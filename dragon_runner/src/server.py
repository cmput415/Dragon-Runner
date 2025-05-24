import os
from typing                         import List, Dict, Any
from dragon_runner.src.cli          import ServerArgs
from dragon_runner.src.runner       import TestResult, ToolChainRunner
from dragon_runner.src.toolchain    import ToolChain
from dragon_runner.src.config       import load_config, Config
from dragon_runner.src.utils        import bytes_to_str, file_to_base64
from dragon_runner.src.testfile     import TestFile
from tempfile                       import NamedTemporaryFile
from pathlib                        import Path
from flask                          import Blueprint, Flask, request, jsonify, current_app
from flask_cors                     import CORS

SERVER_MODE     = os.environ.get("DR_SERVER_MODE", "DEBUG").upper()
IS_PRODUCTION   = (SERVER_MODE == "PROD")
app             = Flask(__name__)
CORS(app)

class Payload:
    def __init__(self):
        self.data = {}

    def to_dict(self):
        return self.data

class ConfigPayload(Payload):
    def __init__(self, config: Config):
        self.data = {
            "name": config.name,
            "executables": [e.id for e in config.executables],
            "toolchains": [t.name for t in config.toolchains]
        }

class ToolChainPayload(Payload):
    def __init__(self, tc: ToolChain):
        self.data = tc.to_dict()

class TestPayload(Payload):
    def __init__(self, test: TestFile):
        self.data = test.to_dict()
        self.data.update({"content": file_to_base64(test.path)})    

class ConfigAPI:
    def __init__(self, config: Config):
        self.config = config
        self.name = Path(config.config_path).stem
        self.tests: Dict = self.unpack_tests()        
        
        # Create blueprint for this config
        self.bp = Blueprint(f"config_{self.name}", __name__)
        self._register_routes()
    
    def unpack_tests(self) -> Dict:
        # Compute tests dictionary only once for each config
        tests = {} 
        for pkg in self.config.packages:
            for spkg in pkg.subpackages:
                for test in spkg.tests:
                    tests[test.file] = test
        return tests

    def _register_routes(self):
        self.bp.route(f"/config/{self.name}", methods=["GET"])(self.get_config)
        self.bp.route(f"/config/{self.name}/toolchains", methods=["GET"])(self.get_toolchains)
        self.bp.route(f"/config/{self.name}/tests", methods=["GET"])(self.get_tests)
        self.bp.route(f"/config/{self.name}/run", methods=["POST"])(self.run_test)
   
    def get_config(self):    
        return jsonify(ConfigPayload(self.config).to_dict())
   
    def get_toolchains(self): 
        return jsonify([ToolChainPayload(t).to_dict() for t in self.config.toolchains]) 
    
    def get_tests(self):
        return jsonify([TestPayload(t).to_dict() for t in self.tests.values()])
    
    def run_test(self):
        data = request.get_json(silent=True) or {}
        test_contents = data.get('test_contents', "int main() { return 0; }")
        toolchain_name = data.get('toolchain_name', "")
        exe_name = data.get('exe_name', "")
        
        try: 
            # Find toolchain and executable
            exe = next((e for e in self.config.executables if e.id == exe_name), 
                      self.config.executables[0])
            tc = next((x for x in self.config.toolchains if x.name == toolchain_name), 
                     self.config.toolchains[0])
            tc_runner = ToolChainRunner(tc, timeout=2)
            
            # create a temporary file to use for runtime supplied test
            with NamedTemporaryFile(mode='w+', delete=True) as temp:
                temp.write(test_contents)
                temp.flush()
                temp.seek(0) 
                test = TestFile(temp.name)

                # run test
                tr: TestResult = tc_runner.run(test, exe)
                gen_output = bytes_to_str(tr.gen_output) if tr.gen_output is not None else ""
                exp_output = bytes_to_str(test.expected_out) if isinstance(test.expected_out, bytes) else ""
                return jsonify({
                    "config": self.name,
                    "test": test.stem,
                    "results": {
                        "passed": tr.did_pass,
                        "exit_status": tr.command_history[-1].exit_status,
                        "generated_output": gen_output,
                        "expected_output": exp_output
                    }
                })
        except Exception as e:
            app.logger.error(f"Error running test: {str(e)}")
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500

@app.route("/")
def root():
    """
    Base route that lists all available routes
    """
    return jsonify({
        "service": "Dragon Runner API",
        "status": "running",
        "mode": "production",
        "available_endpoints": [route['url'] for route in get_available_routes()]
    })
    
def get_available_routes() -> List[Dict[str, Any]]:
    """
    Helper function to list all available routes
    """
    routes = []
    for rule in current_app.url_map.iter_rules():
        if rule.endpoint != 'static' and rule.methods: 
            routes.append({
                "url": str(rule),
                "methods": list(rule.methods - {"OPTIONS", "HEAD"})
            })
    return routes

def get_configs_to_serve(config_dir: Path) -> List[Config]:
    """
    Get all config files from a directory and its subdirectories
    """
    configs: List[Config] = []
    
    def fill_config(path: Path):
        if path.is_file():
            config = load_config(str(path))
            if config is not None:
                configs.append(config)
            return
        
        # Make a recursive call to each file in the directory
        for entry in path.iterdir():
            if entry.is_dir() or entry.is_file():
                fill_config(entry)
    
    fill_config(config_dir)
    return configs

def create_app(args: ServerArgs):
    """
    Create App for WSGI deployment
    """
    configs = get_configs_to_serve(args.serve_path)  
 
    def root_route():
        return jsonify([ConfigPayload(c).to_dict() for c in configs])   
    
    bp = Blueprint(f"configs", __name__)
    bp.route("/configs", methods=["GET"])(root_route)
    app.register_blueprint(bp)

    # create APIs for each config and register their blueprints
    for config in configs:
        api = ConfigAPI(config)
        app.register_blueprint(api.bp)
    
    return app

def serve(args: ServerArgs):
    create_app(args)
    
    if IS_PRODUCTION:
        from wsgiref.simple_server import make_server
        server = make_server('0.0.0.0', args.port, app)
        print(f"Production server running on http://0.0.0.0:{args.port}")
        server.serve_forever()
    else:
        print(f"Dev mode - Flask dev server on http://0.0.0.0:{args.port}")
        app.run(debug=True, host="0.0.0.0", port=args.port)

