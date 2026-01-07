import requests

from me3_manager.core.config_facade import ConfigFacade

# Load API key from saved config
config = ConfigFacade()
API_KEY = config.get_nexus_api_key()
if not API_KEY:
    print("No Nexus API key found! Please login first.")
    exit(1)

GAME_DOMAIN = "eldenringnightreign"
SEARCH_TERM = "storm control"

query = f"""
query {{
  mods(
    filter: {{
      name: [{{ value: "{SEARCH_TERM}", op: WILDCARD }}]
      gameDomainName: [{{ value: "{GAME_DOMAIN}", op: EQUALS }}]
    }}
  ) {{
    nodes {{
      modId
      name
      summary
      author
      downloads
      endorsements
      version
      pictureUrl
    }}
  }}
}}
"""

response = requests.post(
    "https://api.nexusmods.com/v2/graphql",
    headers={"apikey": API_KEY},
    json={"query": query},
)

print(response.json())
