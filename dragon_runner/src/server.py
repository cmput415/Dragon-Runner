from typing import List, Dict, Any, Set
from flask import Flask, jsonify, current_app
from flask import request
from dragon_runner.src.cli import ServerArgs
from dragon_runner.src.runner import TestResult, ToolChainRunner
from dragon_runner.src.config import load_config, Config
from pathlib import Path
from flask import Blueprint, jsonify, request
from dragon_runner.src.testfile import TestFile
from tempfile import NamedTemporaryFile
from dragon_runner.src.utils import bytes_to_str

app = Flask(__name__)

class ConfigAPI:
    def __init__(self, config: Config):
        self.config = config
        self.name = Path(config.config_path).stem
        self.tests: Dict = {}
        
        # Compute tests dictionary only once for each config
        for pkg in config.packages:
            for spkg in pkg.subpackages:
                for test in spkg.tests:
                    self.tests[test.file] = test
        
        # Create blueprint for this config
        self.bp = Blueprint(f"config_{self.name}", __name__)
        self._register_routes()
    
    def _register_routes(self):
        self.bp.route(f"/config/{self.name}", methods=["GET"])(self.get_config)
        self.bp.route(f"/config/{self.name}/tests", methods=["GET"])(self.get_tests)
        self.bp.route(f"/config/{self.name}/run", methods=["POST"])(self.run_test)
    
    def get_config(self):
        return jsonify(self.config.to_dict())
    
    def get_tests(self):
        return jsonify({"tests": [test.to_dict() for test in self.tests.values()]})
    
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
            
            print("Found: ", exe, tc)
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
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500


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

# Usage in your serve function
def serve(args: ServerArgs):
    configs = get_configs_to_serve(args.serve_path)
    
    # Create APIs for each config and register their blueprints
    for config in configs:
        api = ConfigAPI(config)
        app.register_blueprint(api.bp)
    
    app.run(debug=True, host="0.0.0.0", port=args.port)

### ================================ ###
#               DEBUG                  #
### ================================ ###

@app.route("/")
def hello_world():
    """
    Base route that lists all available routes
    """
    routes = get_available_routes()
    route_list = "<h1>Dragon Runner Configs</h1><ul>"
    for route in routes:
        route_list += f"<li><a href='{route['url']}'>{route['url']}</a> - \
                        Methods: {', '.join(route['methods'])}</li>"
    route_list += "</ul>" 
    return f"{route_list}"

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

