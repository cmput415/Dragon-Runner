import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterator, List, Optional


@dataclass
class StudentRecord:
    sid: str
    ccid: str
    github_id: str
    repos: Dict[str, str] = field(default_factory=dict)  # assignment -> repo name


class Key:
    def __init__(self, key_path: Path):
        self.key_path = key_path
        self._records: List[StudentRecord] = []
        self._by_sid: Dict[str, StudentRecord] = {}
        self._by_ccid: Dict[str, StudentRecord] = {}
        self._by_github: Dict[str, StudentRecord] = {}
        self.assignments: List[str] = []

        with open(key_path, newline='') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            if len(headers) < 3:
                raise ValueError(f"Key file must have at least SID,CCID,GitHubID columns, got: {headers}")

            self.assignments = headers[3:]

            for row in reader:
                vals = list(row.values())
                sid, ccid, github_id = vals[0].strip(), vals[1].strip(), vals[2].strip()
                repos = {}
                for i, assignment in enumerate(self.assignments):
                    val = vals[3 + i].strip() if vals[3 + i] else ""
                    if val:
                        repos[assignment] = val

                rec = StudentRecord(sid=sid, ccid=ccid, github_id=github_id, repos=repos)
                self._records.append(rec)
                self._by_sid[sid] = rec
                self._by_ccid[ccid] = rec
                self._by_github[github_id] = rec

    def get(self, identifier: str) -> Optional[StudentRecord]:
        """Lookup by any of SID, CCID, or GitHubID."""
        return self._by_sid.get(identifier) or self._by_ccid.get(identifier) or self._by_github.get(identifier)

    def iter_students(self) -> Iterator[StudentRecord]:
        return iter(self._records)

    def iter_repos(self, assignment: str) -> Iterator[str]:
        """Unique repo names for an assignment."""
        seen = set()
        for rec in self._records:
            repo = rec.repos.get(assignment)
            if repo and repo not in seen:
                seen.add(repo)
                yield repo

    def students_for_repo(self, assignment: str, repo: str) -> List[StudentRecord]:
        """Team members sharing a repo for an assignment."""
        return [rec for rec in self._records if rec.repos.get(assignment) == repo]

    def get_repo(self, identifier: str, assignment: str) -> Optional[str]:
        """Repo for a student + assignment."""
        rec = self.get(identifier)
        if rec is None:
            return None
        return rec.repos.get(assignment)
