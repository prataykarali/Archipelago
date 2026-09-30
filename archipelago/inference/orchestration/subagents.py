"""
Archipelago Orchestration Subagents
"""
import re
from typing import Dict, Any, List, Optional
from archipelago.inference.orchestration.okf_facets import OKFFacets

class OrchestratorAgent:
    def __init__(self):
        self.injection_patterns = [
            r"ignore previous instructions",
            r"print system prompt",
            r"show database password",
            r"cat /etc/passwd"
        ]
        self.code_gen_patterns = [
            r"write python script",
            r"docker config",
            r"bash script",
            r"git command"
        ]
        self.homework_patterns = [
            r"write \d+-word essay",
            r"assignment question",
            r"draft email to professor"
        ]
        self.web_patterns = [
            r"search the web",
            r"scrape",
            r"browse internet",
            r"http://"
        ]

    def intercept(self, query: str) -> Dict[str, Any]:
        if len(query) > 500:
            raise ValueError("Payload length exceeds 500 characters ceiling.")

        # Strip conversational pleasantries (naive)
        query = re.sub(r"^(please|kindly|hello|hi|thanks)\b", "", query, flags=re.IGNORECASE).strip()

        # Prompt injection check
        for pat in self.injection_patterns:
            if re.search(pat, query, re.IGNORECASE):
                return {"status": "denied", "reason": "SECURITY_DISCLAIMER: Unauthorized prompt injection detected."}

        # Code gen check
        for pat in self.code_gen_patterns:
            if re.search(pat, query, re.IGNORECASE):
                return {"status": "denied", "reason": "THEORETICAL_BOUNDARY: Code generation and DevOps execution are out of scope."}

        # Homework check
        for pat in self.homework_patterns:
            if re.search(pat, query, re.IGNORECASE):
                return {"status": "denied", "reason": "ACADEMIC_INTEGRITY: Artifact drafting and direct assignment solving are not permitted."}

        # Live web check
        for pat in self.web_patterns:
            if re.search(pat, query, re.IGNORECASE):
                return {"status": "denied", "reason": "LOCAL_BOUNDARY: Live web browsing is restricted to local library indices."}

        return {"status": "ok", "query": query, "route": "unknown"}

class SimilarityFirewallAgent:
    def __init__(self):
        self.commercial_entities = ["aws", "openai", "google translate", "taylor swift"]
        
    def check_similarity(self, query: str, similarity_score: float) -> Optional[str]:
        if similarity_score < 0.75:
            return "OUT_OF_SCOPE: Query similarity below 0.75 threshold."
        
        query_lower = query.lower()
        if any(entity in query_lower for entity in self.commercial_entities):
            return "OUT_OF_SCOPE: Commercial brand and platform queries are denied."
            
        return None

class PedagogicalTraversalAgent:
    def traverse(self, source: str, target: str, k: int = 2, path_exists: bool = False) -> str:
        if k <= 2 and not path_exists:
            return OKFFacets.unrelated_denial(source, target)
        return f"Traversing from {source} to {target}"

class CriticSynthesisAgent:
    def synthesize(self, text: str) -> str:
        # Regex-strips internal file paths, /tmp, or broken URLs
        text = re.sub(r"(/tmp/[^\s]+|/var/[^\s]+|/[^\s]*\.py)", "[REDACTED_PATH]", text)
        text = re.sub(r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+", "[REDACTED_URL]", text)
        return text

class RecoveryAgent:
    def handle_fallback(self, concept: str, parent: str) -> str:
        return OKFFacets.catalog_depth_fallback(concept, parent)

class CatalogInventoryAgent:
    def lookup(self, items: List[Dict[str, Any]]) -> str:
        return OKFFacets.catalog_shelf_routing(items)

class RoutineNavigationAgent:
    def get_info(self, topic: str) -> str:
        mapping = {
            "hours": "Library Hours: 8AM - 10PM",
            "contact": "Librarian Contact: librarian@archipelago.edu"
        }
        return mapping.get(topic.lower(), "Information not found.")

class AuthGatewayAgent:
    def require_auth(self, resource: str) -> str:
        paywalls = ["ieee xplore", "sciencedirect", "scopus", "ndli", "ieee", "scopus"]
        res_lower = resource.lower()
        for pw in paywalls:
            if pw in res_lower:
                return OKFFacets.auth_gateway(pw.upper())
        return "Access Granted"

class DiagnosticMCQAgent:
    def generate_mcqs(self, questions: List[Dict[str, Any]]) -> Dict[str, Any]:
        return OKFFacets.mcq_diagnostic(questions)

class ContextTrackerAgent:
    def __init__(self):
        self.session_map = {}
        self.idle_timeout = 300
        
    def track(self, session_id: str, node: str, time_elapsed: int):
        if time_elapsed > self.idle_timeout:
            return "SESSION_TIMEOUT: Session idle."
        if session_id not in self.session_map:
            self.session_map[session_id] = []
        self.session_map[session_id].append(node)
        return "TRACKED"
