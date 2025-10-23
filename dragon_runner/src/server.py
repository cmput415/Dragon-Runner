import os
import subprocess
import shutil
from typing import                      List, Dict, Any, Optional
from dragon_runner.src.cli import       ServerArgs
from dragon_runner.src.runner import    TestResult, ToolChainRunner, Command, CommandResult
from dragon_runner.src.toolchain import ToolChain
from dragon_runner.src.config import    load_config, Config, Executable
from dragon_runner.src.testfile import  TestFile
from dragon_runner.src.utils import *
from tempfile import                    NamedTemporaryFile
from pathlib import                     Path
from flask import                       Blueprint, Flask, request, jsonify, current_app, \
                                        send_from_directory
from flask_cors import                  CORS

SERVER_MODE = os.environ.get("DR_SERVER_MODE", "DEBUG").upper()
STATIC_DIR = os.environ.get("DR_STATIC_DIR", "")
IS_PRODUCTION = (SERVER_MODE == "PROD")

if STATIC_DIR == "" or not os.path.exists(STATIC_DIR):
    print("Must supply a static directory to serve.", file=sys.stderr)
    exit(1)

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path='')
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
        self.data.update({"content": utf8_file_to_base64(test.path)})    

class ConfigAPI:
    def __init__(self, config: Config):
        self.config = config
        self.config_path = config.config_path
        self.name = Path(config.config_path).stem
        self.tests: Dict = self.unpack_tests()        
        
        # Create blueprint for this config
        self.bp = Blueprint(f"config_{self.name}", __name__)
        self._register_routes()
    
    def unpack_tests(self) -> Dict:
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
        exe_name: str = data.get('exe_name', "")
        test_stdin: Optional[bytes] = b64_to_bytes(data.get('stdin', ""))
        test_contents: Optional[str] = b64_to_str(data.get('test_contents', ""))
    
        if test_stdin is None or test_contents is None:
            app.logger.error(f"Test received stdin: {test_stdin} and contents {test_contents}")
            return jsonify({
                "status": "error",
                "message": "Failed to decode stdin and/or test contents in request."
            }), 500
        
        try:
            import time
            exe = next((e for e in self.config.executables if e.id == exe_name), 
                      self.config.executables[0]) 
            with NamedTemporaryFile(mode='w+', delete=True, suffix='.test', dir='/tmp') as temp:
                temp.write(test_contents)
                temp.flush()
                temp.seek(0) 
                compile_step = subprocess.run(["/usr/bin/gazc", temp.name, "/tmp/gazprea.out"], 
                                               capture_output=True)
                if compile_step.returncode != 0:
                    return jsonify({
                        "config": self.name,
                        "test": temp.name,
                        "results": {
                            "passed": False,
                            "exit_status": compile_step.returncode,
                            "stdout": bytes_to_b64(b''),
                            "stderr": bytes_to_b64(compile_step.stderr),
                            "time": 0,
                            "expected_output": bytes_to_b64(b''),
                        }
                    })
                
                start = time.time()
                run_step = subprocess.run(["lli", "/tmp/gazprea.out"], 
                                           capture_output=True,
                                           input=test_stdin,
                                           env={**os.environ, "LD_PRELOAD": "/usr/lib/libgazrt.so"})
                elapsed = time.time() - start 
                return jsonify({
                    "config": self.name,
                    "test": temp.name,
                    "results": {
                        "passed": run_step.returncode == 0,
                        "exit_status": run_step.returncode,
                        "stdout": bytes_to_b64(run_step.stdout),
                        "stderr": bytes_to_b64(run_step.stderr),
                        "time": elapsed,
                        "expected_output": bytes_to_b64(b''),
                    }
                })
        except subprocess.TimeoutExpired:
            app.logger.error("Test execution timed out")
            return jsonify({
                "status": "error",
                "message": "Test execution timed out"
            }), 408
        except Exception as e:
            app.logger.error(f"Error running test: {str(e)}")
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def root(path):
    if path and os.path.exists(os.path.join(STATIC_DIR, path)):
        return send_from_directory(STATIC_DIR, path)
    return send_from_directory(STATIC_DIR, 'index.html')

@app.route("/health")
def health():
    """Base route that lists all available routes"""
    return jsonify({
        "service": "Dragon Runner API",
        "status": "running",
        "mode": "production" if IS_PRODUCTION else "debug",
        "available_endpoints": [route['url'] for route in get_available_routes()]
    })
    
def get_available_routes() -> List[Dict[str, Any]]:
    """Helper function to list all available routes"""
    routes = []
    for rule in current_app.url_map.iter_rules():
        if rule.endpoint != 'static' and rule.methods: 
            routes.append({
                "url": str(rule),
                "methods": list(rule.methods - {"OPTIONS", "HEAD"})
            })
    return routes

def get_configs_to_serve(config_dir: Path) -> List[Config]:
    """Get all config files from a directory and its subdirectories"""
    configs: List[Config] = []
    
    def fill_config(path: Path):
        if path.is_file():
            config = load_config(str(path))
            if config is not None:
                configs.append(config)
            return
        
        for entry in path.iterdir():
            if entry.is_dir() or entry.is_file():
                fill_config(entry)
    
    fill_config(config_dir)
    return configs

def create_app(args: ServerArgs):
    """Create App for WSGI deployment"""
    configs = get_configs_to_serve(args.serve_path)  
 
    def root_route():
        return jsonify([ConfigPayload(c).to_dict() for c in configs])   
    
    bp = Blueprint(f"configs", __name__)
    bp.route("/configs", methods=["GET"])(root_route)
    app.register_blueprint(bp)

    # Create APIs for each config and register their blueprints
    for config in configs:
        api = ConfigAPI(config)
        app.register_blueprint(api.bp)
    
    # Log security status
    firejail_status = "ENABLED" if shutil.which('firejail') else "DISABLED"
    app.logger.info(f"Security sandbox: {firejail_status}")
    
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

