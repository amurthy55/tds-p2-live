# app/phase2_script_builder.py
import re
import json
import logging
from app.config import STUDENT_EMAIL

logger = logging.getLogger("phase2.script_builder")


def _make_prompt(facts, current_url, previous_error=None, attempt_number=0):
    """
    Strict code-only prompt. Model MUST output:

    #PYTHON_START
    final_answer = ...
    #PYTHON_END
    """

    base_prompt = f"""
You produce ONLY Python code inside:
#PYTHON_START
#PYTHON_END

================= ABSOLUTE RULES (DO NOT BREAK) =================
1. Output ONLY Python — NO text, NO explanations, NO markdown, NO backticks.
2. Code MUST define: final_answer = <value>
3. NOTHING is allowed outside #PYTHON_START / #PYTHON_END.
4. For GitHub tree tasks: You MUST fetch the tree API using requests.get()
5. For other tasks: Use ONLY provided facts & local attachments (no network calls)
6. Do NOT print anything except the final JSON stub (already wrapped).

7. final_answer must NEVER be:
   - None
   - null
   - empty string
   - empty list
   - empty dict

   If you cannot determine a correct meaningful answer, set:
       final_answer = "pass"

================= PROBLEM-SOLVING APPROACH =================
IMPORTANT: The examples below are PATTERNS to adapt, NOT rigid templates.
- Always READ the task description carefully to understand what's being asked
- INSPECT the data first (columns, structure, sample values)
- ADAPT the solution to the actual data and requirements
- The exact column names, formulas, and logic will vary by task
- Use the file type guidance as general strategies, not exact scripts

================= FILE TYPE RULES (MANDATORY) =================

⚠️ CRITICAL: Check attachment filenames FIRST before making assumptions ⚠️
- If attachment is "logs.zip", check what's INSIDE (likely logs.jsonl)
- If filename ends with ".jsonl", it's JSON-per-line, NOT CSV
- DO NOT look for CSV files that don't exist

CSV FILES:
- ALWAYS load using pandas.read_csv(<local_path>).
- NEVER assume column names - use the ACTUAL column names from the CSV.
- ALWAYS inspect real columns first using:
      data.columns.tolist()
- Normalize column names ONLY by:
      data.columns = [str(c).strip().lower().replace(" ", "_") for c in data.columns]
- After normalization, identify which columns to use based on the task:
      * Read the task description to understand what fields are needed
      * Use the actual column names, NOT hardcoded assumptions
      * For example: if task mentions "customer_id" and "order_date", use those exact names
      * DO NOT try to rename columns to generic names like "id, name, joined, value"
      * To find columns, use exact matching: 'customer_id' in data.columns
      * Avoid data.columns.str.contains() - it fails with IndexError
      * Just use the column names directly as they appear in the task
- NEVER invent data.
- NEVER drop rows unless explicitly instructed.
- For ANY date columns (order_date, joined, date, etc.):
      * CRITICAL: Convert the ENTIRE column BEFORE list comprehension or iteration
      * Parse with pd.to_datetime() to handle mixed formats
      * IMPORTANT: Use dayfirst=True for ambiguous dates like "02/01/24"
      * Apply .dt.strftime() to the SERIES, not to individual row values
      * CORRECT: data['joined'] = pd.to_datetime(data['joined'], dayfirst=True).dt.strftime('%Y-%m-%d')
      * WRONG: row['joined'] = pd.to_datetime(row['joined'], dayfirst=True).dt.strftime('%Y-%m-%d')
      * The .dt accessor only works on Series, not on scalar Timestamp objects
      * Output as YYYY-MM-DD format (NO time component)
      * NEVER use ISO-8601 with time (no 'T00:00:00')
      * Example: "02/01/24" → "2024-01-02" (day/month/year)
- For numeric columns (amount, value, price, total, etc.):
      * Strip whitespace and convert to appropriate type
      * For money: keep as float or int based on context
      * For counts: convert to int
- Sort ONLY after verifying the sort column exists.
- Output final_answer formatting:
      * If task asks for JSON array, use json.dumps() with NO SPACES
      * Use: json.dumps(records, separators=(',', ':'))
      * This produces: {{"id":1,"name":"Alpha"}} NOT {{"id": 1, "name": "Alpha"}}
      * Match the exact key names requested in the task description
      * Convert values to appropriate types (int, float, str) as specified
      * Example 1 - Records with id/name/joined/value:
        # Convert date column BEFORE iterating (not inside list comprehension!)
        data['joined'] = pd.to_datetime(data['joined'], dayfirst=True).dt.strftime('%Y-%m-%d')
        # Now build records - joined is already a string
        records = [{{
            "id": int(row['id']),
            "name": str(row['name']),
            "joined": row['joined'],  # Already converted to YYYY-MM-DD string
            "value": int(row['value'])
        }} for _, row in data.iterrows()]
        final_answer = json.dumps(records, separators=(',', ':'))
      * Example 2 - Running totals (cumulative sum ordered by date):
        # Sort by date first
        data = data.sort_values('order_date')
        # Compute cumulative sum per customer
        data['running_total'] = data.groupby('customer_id')['amount'].cumsum()
        # Get the final (maximum) running total for each customer
        result = data.groupby('customer_id')['running_total'].max().reset_index()
        result.columns = ['customer_id', 'total']
        # Sort by total descending and take top N
        result = result.sort_values('total', ascending=False).head(3)
        records = [{{
            "customer_id": str(row['customer_id']),
            "total": int(row['total'])
        }} for _, row in result.iterrows()]
        final_answer = json.dumps(records, separators=(',', ':'))
      * Example 3 - Simple aggregation (total sum per group):
        result = data.groupby('customer_id')['amount'].sum().reset_index()
        result.columns = ['customer_id', 'total']
        result = result.sort_values('total', ascending=False)
        records = [{{
            "customer_id": str(row['customer_id']),
            "total": int(row['total'])
        }} for _, row in result.iterrows()]
        final_answer = json.dumps(records, separators=(',', ':'))
- If retry fails with same error:
      * Print data.head() in comments to debug
      * Check actual vs expected column names
      * Verify date format is YYYY-MM-DD (not YYYY-MM-DDTHH:MM:SS)
      * Ensure values are integers, not strings

PDF FILES:
- Use PyPDF2.PdfReader (from PyPDF2 import PdfReader)
- Extract text from all pages:
    reader = PdfReader(local_path)
    text = ''
    for page in reader.pages:
        text += page.extract_text()
- STRATEGY: PDFs may have data on separate lines, not in table format
    * First: Print or examine the text to understand structure
    * Look for column headers to identify what data exists
    * Extract ALL numeric values INCLUDING DECIMALS:
      numbers = re.findall(r'\d+\\.?\d*', text)  # Matches integers AND decimals
      numbers = [float(n) for n in numbers]
    * CRITICAL: Use \d+\\.?\d* NOT \d+ to capture decimal values like 19.99
- For calculations (invoices, tables, etc.):
    * Read the task description to understand the formula
    * Identify which numbers are which based on order/context
    * If task says "sum(Quantity * UnitPrice)", group numbers appropriately
    * Example pattern for 2 values per row:
      # Ensure even number of values before pairing
      if len(numbers) % 2 == 0:
          pairs = [(numbers[i], numbers[i+1]) for i in range(0, len(numbers), 2)]
      total = sum(q * price for q, price in pairs)
    * For 3 values per row: groups = [(numbers[i], numbers[i+1], numbers[i+2]) for i in range(0, len(numbers), 3)]
    * Apply the formula from the task description
- Round financial results to 2 decimals: round(total, 2)
- Return as appropriate type (float for money, int for counts)

IMAGE FILES:
- Use PIL (from PIL import Image) or pillow.
- ALWAYS convert to RGB: img.convert('RGB')
- For color analysis:
    * Use img.getdata() to get pixel list
    * Count colors with collections.Counter
    * Convert RGB tuples to hex: '#%02x%02x%02x' % (r, g, b)
- For pixel comparison:
    * Load both images with same mode (RGB)
    * Use numpy: np.array(img1) vs np.array(img2)
    * Count differences: np.sum(arr1 != arr2) // 3 (for RGB channels)
- Return color hex strings in lowercase (e.g., '#ff5733')
- Return pixel counts as plain integers

AUDIO FILES:
- Use ONLY provided transcription in FACTS.
- Do NOT attempt re-transcription.

ZIP FILES - CRITICAL RULES:
- ALWAYS extract ZIP files using zipfile.ZipFile
- After opening ZIP, use .namelist() to see what files are inside
- DO NOT assume file extensions - check actual filenames in the ZIP

JSONL FILES (*.jsonl) - ABSOLUTE RULES:
⚠️ CRITICAL: JSONL files contain ONE JSON OBJECT PER LINE ⚠️
⚠️ NEVER look for CSV files when you have JSONL ⚠️
⚠️ NEVER use line.split() on JSONL - that's for whitespace data ⚠️

CORRECT approach for JSONL inside ZIP:
    with zipfile.ZipFile(zip_path) as zf:
        # Option 1: Use pandas (BEST for aggregation tasks)
        data = pd.read_json(zf.read('logs.jsonl').decode('utf-8'), lines=True)
        # Now you can filter/aggregate: data[data['event'] == 'download']['bytes'].sum()
        
        # Option 2: Manual parsing
        content = zf.read('file.jsonl').decode('utf-8')
        records = [json.loads(line) for line in content.strip().split('\n')]
        data = pd.DataFrame(records)

WRONG approaches that WILL FAIL:
    ❌ Looking for .csv file when only .jsonl exists
    ❌ Using line.split() on JSON data
    ❌ Extracting to directory instead of reading directly
    ❌ Treating JSONL as regular text file

AGGREGATION TASKS with JSONL:
1. Read task description to identify: filter column, filter value, aggregation column
2. Load JSONL with pd.read_json(lines=True)
3. Filter: filtered = data[data['column'] == 'value']
4. Aggregate: result = filtered['numeric_column'].sum()  # or .mean(), .count()

CRITICAL DISTINCTION:
    * If task asks to "sum X values": Use data['column_name'].sum()
    * If task asks to "count rows": Use len(data) or data.shape[0]
    * Example: "sum bytes" means data['bytes'].sum(), NOT counting rows
- For personalized tasks with email-based offsets:
    * Task description will say "personalized" and mention email length
    * Use the provided EMAIL_LENGTH variable (already calculated)
    * Compute offset: offset = EMAIL_LENGTH % N (where N is from task)
    * Add to base result: final_answer = base_value + offset
    * STUDENT_EMAIL is also available if you need the actual email string

JSON / API RESPONSE FILES:
- If any page contents start with '{{' or '[' and are valid JSON,
  you MUST parse them using json.loads().
- NEVER assume data is missing if JSON is present in FACTS.

TOOL/FUNCTION CALL PLANNING TASKS:
- Some tasks ask you to create a JSON plan of function/tool calls
- The task description will specify:
  * Which tools to call in what order
  * What arguments to pass (e.g., "owner=demo, repo=api, id=42")
- CRITICAL: Use ACTUAL values from the task, NOT placeholder parameter names
  * WRONG: {{"tool": "fetch_issue", "args": ["owner", "repo", "id"]}}
  * CORRECT: {{"tool": "fetch_issue", "args": ["demo", "api", 42]}}
  * WRONG: {{"tool": "search_docs", "args": ["query"]}}
  * CORRECT: {{"tool": "search_docs", "args": ["demo/api issue 42 status"]}}
- STRATEGY:
  1. Parse the tool schema from JSON data to understand parameter names
  2. Read task description to extract the goal and specific values
  3. For EACH tool in the chain, provide meaningful arguments:
     * Search tools: Create specific query string based on what you're looking for
     * Fetch tools: Use actual IDs, owners, repos from task description
     * Summarize tools: Specify what's being summarized and token limits
  4. Respect constraints (e.g., "max_tokens ≤ 80" means use 80 or less, not "max_tokens")
- Example: "find status of issue 42 in repo demo/api and summarize in 60 words":
  * search_docs: args should be a query about the issue ["issue 42 in demo/api"]
  * fetch_issue: args should be the actual repo/issue ["demo", "api", 42]
  * summarize: args should be the text source and limit ["issue content", 60]
  * Full plan:
    [{{"tool":"search_docs","args":["demo/api issue 42"]}},
     {{"tool":"fetch_issue","args":["demo","api",42]}},
     {{"tool":"summarize","args":["issue details",80]}}]

**GITHUB TREE TASKS - CRITICAL:**
- You MUST fetch the actual GitHub tree API data yourself!
- The parameters (owner, repo, sha, pathPrefix, extension) are in the pages
- DO NOT make up fake data or use placeholder counts!

STEP-BY-STEP PROCESS:
1. Parse parameters from the gh-tree.json page:
    import requests
    params = None
    for page in phase1_facts['pages']:
        if 'gh-tree.json' in page.get('url', ''):
            params = json.loads(page['contents'])
            break
    
2. Fetch the ACTUAL GitHub tree API:
    api_url = f"https://api.github.com/repos/{{params['owner']}}/{{params['repo']}}/git/trees/{{params['sha']}}?recursive=1"
    response = requests.get(api_url, timeout=10)
    tree_data = response.json()

3. Count matching files:
    count = 0
    for item in tree_data.get('tree', []):
        if item.get('type') == 'blob':  # files only, not folders
            path = item.get('path', '')
            if path.startswith(params['pathPrefix']) and path.endswith(params['extension']):
                count += 1

4. Add personalization offset (if task mentions email-based offset):
    offset = EMAIL_LENGTH % 2  # Use the modulo value from task description
    final_answer = count + offset

NEVER use simulated/placeholder data - ALWAYS fetch from GitHub API!

================= LOGIC RULES (MANDATORY) =================

CRITICAL: READ THE TASK INSTRUCTIONS IN FACTS CAREFULLY!
- Look for keywords in page contents: "POST as", "submit the", "return", "send"
- Identify what format is requested: string, number, JSON array, etc.

- FIRST understand what the evaluator expects as the *exact answer format*.
- If the task asks to "submit the command string", "submit the exact command",
  "submit that exact string", or similar wording:
      final_answer MUST be a plain string.
      Do NOT wrap it in JSON, dicts, or lists.
- If task says "send the number only", "submit that integer":
      final_answer must be int or float, NOT string
- If task says "POST the JSON array as a string":
      final_answer = json.dumps([...])  # String containing JSON
- If task says "send IDs only" or "comma-separated":
      final_answer = "id1,id2,id3"  # Plain string with commas
- Do NOT return explanations.
- Do NOT repeat a previously incorrect approach.
- If computation involves multiple steps, show your work in comments


- Difficulty awareness:
    - Difficulty 1–2: incorrect answers may still advance.
    - Difficulty 3+: next URL is revealed ONLY on correct answer.
      Do NOT use "pass" if sufficient data is available.

================= TASK-SPECIFIC PATTERNS =================

CONSTRAINT OPTIMIZATION TASKS:
- Some tasks ask you to find values that satisfy multiple constraints
- STRATEGY:
  1. Parse all constraints from JSON data
  2. Identify what variables need to be chosen (e.g., shards, replicas)
  3. Understand ALL constraint formulas (carefully read each one)
  4. CRITICAL: Account for ALL variables in constraint calculations
     * If memory depends on shards AND replicas: memory = shards × replicas × per_unit
     * Don't forget to multiply by all relevant variables
  5. Test all valid combinations within bounds
  6. Return the solution that satisfies ALL constraints
- Example: If choosing shards & replicas with memory_budget constraint:
  * Memory formula: total_memory = shards × replicas × memory_per_shard
  * Must be: total_memory ≤ memory_budget
  * Loop through all combinations and filter valid ones

STRING/COMMAND TASKS:
- Return exact strings as specified (no quotes inside the string)
- For URL construction: use window.location.origin from JS or build from base URL
- For file paths: return exact path as shown (e.g., '/project2/file.ext')

CHOICE/KNOWLEDGE TASKS:
- If asked for single letter/option: return just the letter (e.g., 'B')
- For YAML/code snippets: return properly formatted multi-line strings
- For system prompts: use clear bullet points or numbered lists

COMPLEX JSON TASKS:
- For optimization problems (shards, rate limits):
    * Parse constraints from JSON carefully
    * Use mathematical reasoning or iteration to find valid solutions
    * Example: Find shards/replicas satisfying all constraints
      for shards in range(1, max_shards+1):
          for replicas in range(min_rep, max_rep+1):
              if all_constraints_satisfied(shards, replicas):
                  final_answer = json.dumps({{"shards": shards, "replicas": replicas}})
    * Return as specified format (plain JSON string or dict)
- For ranking/scoring (RAG, embeddings, F1):
    * Compute scores exactly as formula specifies
    * Example RAG: score = 0.6 * lex + 0.4 * vector
      chunks = [{{"id": x["id"], "score": 0.6*x["lex"] + 0.4*x["vec"]}} for x in data]
      chunks.sort(key=lambda x: x["score"], reverse=True)
      top3_ids = [c["id"] for c in chunks[:3]]
      final_answer = ",".join(top3_ids)
    * For F1 metrics: F1 = 2*tp / (2*tp + fp + fn) per label, then average
    * Sort by score descending
    * Return top N items in correct format
- For tool planning:
    * Return JSON array of tool calls with exact schema
    * Example: [{{"tool": "search_docs", "args": {{...}}}}, {{"tool": "fetch_issue", "args": {{...}}}}]
    * Include all required arguments
    * Preserve order as specified

PERSONALIZATION:
- Email length is provided as EMAIL_LENGTH in facts
- Apply modulo operations exactly: (EMAIL_LENGTH mod N)
- Add offset to base calculations when instructed
- For conditional logic based on email length:
    * If even: use one value
    * If odd: use another value
    * Check with: EMAIL_LENGTH % 2 == 0

If PREVIOUS_ERROR is provided:
- It is evaluator feedback.
- You MUST change your logic to address it.
- NEVER repeat the same mistake.

================= OUTPUT FORMAT EXAMPLES =================

Plain string (command/path):
    final_answer = "uv http get https://example.com/file.json -H \"Accept: application/json\""
    final_answer = "/project2/data-preparation.md"

Single letter/number:
    final_answer = "B"
    final_answer = 42

Float/decimal:
    final_answer = 123.45

JSON string (from list/dict):
    final_answer = json.dumps([{{"id": 1, "name": "test"}}])
    final_answer = json.dumps({{"shards": 5, "replicas": 2}})

Comma-separated IDs:
    final_answer = "s4,s5"
    final_answer = "chunk1,chunk2,chunk3"

Multi-line text (YAML, prompts):
    final_answer = \"\"\"- uses: actions/cache@v4
  with:
    path: ~/.npm
    key: ${{{{ hashFiles('**/package-lock.json') }}}}
    restore-keys: |
      npm-\"\"\"

================= FACTS PROVIDED =================
{json.dumps(facts, indent=2)}

================= CONTEXT =================
CURRENT_URL: {current_url}
STUDENT_EMAIL: {facts.get("student_email")}
EMAIL_LENGTH: {len(facts.get("student_email") or "")}
ATTEMPT_NUMBER: {attempt_number}
"""

    if previous_error:
        base_prompt += f"""
================= PREVIOUS_ERROR (Evaluator Feedback) =================
{previous_error}
"""

    base_prompt += """
Return ONLY the Python code between the markers.
ABSOLUTELY NOTHING ELSE.
"""

    return base_prompt




def extract_llm_code(raw: str) -> str:
    """
    Extracts code inside #PYTHON_START ... #PYTHON_END
    """

    m = re.search(r"#PYTHON_START(.*?)#PYTHON_END", raw, re.DOTALL)
    if not m:
        raise ValueError("LLM did not return a #PYTHON_START/#PYTHON_END block.")

    body = m.group(1).strip()

    # 1. Must assign final_answer
    if not re.search(r"\bfinal_answer\s*=", body):
        raise ValueError("LLM did not assign final_answer.")

    # 2. Must not contain markdown fences
    if "```" in body:
        raise ValueError("LLM output contains markdown fences.")

    # 3. Nothing else — Python execution is the validator
    return body




import re
import json
import logging
import pprint   # <--- add this

logger = logging.getLogger("phase2.script_builder")

# ... keep existing functions ...

def build_script(facts, llm_raw, start_url):
    """
    Wraps extracted safe LLM python block into full executable code.
    """

    code = extract_llm_code(llm_raw)

    # Use pprint.pformat to get a Python-valid representation (None/True/False, not null/true/false)
    facts_py = pprint.pformat(facts)

    student_email = facts.get("student_email")
    # Fallback: extract email from URL if not in facts
    if not student_email and start_url:
        import re
        email_match = re.search(r'email=([^&]+)', start_url)
        if email_match:
            student_email = email_match.group(1).replace('%40', '@')
    student_email = student_email or ""
    email_length = len(student_email)

    wrapper = f"""
import json
import numpy as np
import pandas as pd
import re
import requests
from collections import Counter
from pathlib import Path

phase1_facts = {facts_py}
current_url = {json.dumps(start_url)}
STUDENT_EMAIL = {json.dumps(student_email)}
EMAIL_LENGTH = {email_length}

# === LLM CODE ===
{code}
# === END LLM CODE ===

try:
    final_answer
except NameError:
    raise RuntimeError("LLM did not set final_answer")

# cast numpy/pandas scalars to python
try:
    if hasattr(final_answer, "item"):
        final_answer = final_answer.item()
except:
    pass

print(json.dumps({{"answer": final_answer}}))
"""
    return wrapper
