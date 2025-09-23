from typing import Tuple
from pathlib import Path
from typing import Iterator

class Key: 
    def __init__(self, key_path: Path):
        self.key_path = key_path
        self.sid_repo_suffix_map = {}

        with open(key_path) as key_file: 
            for line in key_file.readlines():
                sids, repo_suffix = line.strip().split(' ')
                sid_list = sids.strip().split(',') 
                for sid in sid_list:
                    self.sid_repo_suffix_map[sid] = repo_suffix
    
    def __str__(self):
        s = ""
        for k, v in self.sid_repo_suffix_map.items():
            s += (f"{k}\t{v}")
        return s
    
    def get_repo_for_sid(self, sid):
        return self.sid_repo_suffix_map[sid]
    
    def iter_sids(self) -> Iterator[str]:
        return iter(self.sid_repo_suffix_map.keys())

    def iter_repos(self) -> Iterator[str]:
        return iter(set(self.sid_repo_suffix_map.values()))

    def iter_both(self) -> Iterator[Tuple[str, str]]:
        return iter(self.sid_repo_suffix_map.items())

