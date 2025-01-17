from dotenv import load_dotenv
from griptape.structures import Agent
from griptape.tools import PromptSummaryTool, WebScraperTool
# import json

load_dotenv()  # Load environment variables

# 1) Create an Agent with the web scraping and summarization tools
agent_scraper = Agent(tools=[
    WebScraperTool(off_prompt=True),
    PromptSummaryTool(off_prompt=False)
])

# 2) Scrape the website and store the output
scraped_run = agent_scraper.run(
    "Summarize this article: https://www.quantamagazine.org/heat-destroys-all-order-except-for-in-this-one-special-case-20250116/"
)

#scraped_run

#print("Here is the final text:")
#print(json.dumps(scraped_run))
#print(dir(scraped_run))

# print(f"scarped output: {scraped_run.output}")

scraped_output = scraped_run.output



# 3) Now create a second Agent for the final prompt
agent_prompt = Agent()

# 4) Combine the scraped output with your instructions
final_input = (
    f"{scraped_output}\n\n"
    "You are a master illustrator. Write a descriptive image prompt for stable diffusion "
    "that effectively illustrates the article above. Focus on the subject of the article as "
    "the main element of the graphic and start the prompt with that. The style of the image "
    "should be: graphic design, swiss style, retro futurism, art deco, bauhaus, modern. "
    "only write the prompt."
)

# 5) Run the second agent and print/return the result
# response = agent_prompt.run(final_input)
response = agent_prompt.run(final_input)
print(response.output)
