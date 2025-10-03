from langchain.tools import tool

def lookup_statute(statute_id: str) -> str:
    """Look up a statute by ID from the legal statute database."""
    statutes = {
        "123": "Contract Act Section 123: All contracts must be lawful, and the object and consideration of every agreement must be lawful.",
        "124": "Contract Act Section 124: A contract by which one party promises to save the other from loss caused to him by the conduct of the promisor himself, or by the conduct of any other person, is called a 'contract of indemnity'.",
        "125": "Contract Act Section 125: A 'guarantee' is a contract to perform the promise, or discharge the liability, of a third person in case of his default.",
    }
    
    statute_id = statute_id.strip().lower()
    
    result = statutes.get(statute_id)
    if result:
        return result
    
    return f"Statute '{statute_id}' not found in the legal database."

class StatuteLookup:
    def __init__(self):
        self.name = "lookup_statute"
        
    def run(self, statute_id: str) -> str:
        return lookup_statute(statute_id)

# Create instance for import compatibility
lookup_statute_tool = StatuteLookup()