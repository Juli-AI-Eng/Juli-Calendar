"""AI-powered test grader using GPT-4-mini for flexible E2E test validation."""
import os
import json
from typing import Dict, Any, Optional, Tuple
import re
from dataclasses import dataclass
import openai
from colorama import init, Fore, Style
from datetime import datetime

# Initialize colorama for cross-platform colored output
init()

@dataclass
class GradingResult:
    """Result of AI grading."""
    passed: bool
    reasoning: str
    confidence: float
    details: Optional[Dict[str, Any]] = None


class AITestGrader:
    """AI-powered test grader using GPT-4-mini."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the grader with OpenAI API key."""
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key required. Set OPENAI_API_KEY environment variable.")
        
        self.client = openai.OpenAI(api_key=self.api_key)
    
    def grade_response(
        self,
        test_name: str,
        expected_behavior: str,
        request_data: Dict[str, Any],
        response_data: Dict[str, Any]
    ) -> GradingResult:
        """Grade a test response using AI."""
        # Prepare the grading prompt
        prompt = self._build_grading_prompt(
            test_name, expected_behavior, request_data, response_data
        )
        
        try:
            # Call GPT-5-mini via Responses API (no Completions fallback)
            system_text = (
                "You are an expert, fair, and literal test grader for a productivity management system that integrates "
                "calendar events (Nylas) and tasks (Reclaim.ai). You understand approval flows, conflict detection, "
                "duplicate detection, and various response formats. Grade based on semantic correctness, not exact string "
                "matches. CRITICAL RULES: (1) Grade ONLY the behavior described in EXPECTED BEHAVIOR. The TEST NAME is just a label "
                "and must NOT cause you to require additional steps beyond EXPECTED BEHAVIOR. (2) If EXPECTED BEHAVIOR says 'after approval if needed', "
                "then BOTH of these are valid PASS outcomes: either a direct success (success=true, action done) with no needs_approval flag, OR a needs_approval=true response with appropriate action_type. "
                "(3) Warnings (e.g., 'This event involves other people') do NOT by themselves require approval; treat them as informational. "
                "(4) Approve or disapprove solely on whether the ACTUAL RESPONSE fulfills EXPECTED BEHAVIOR for THIS STEP."
            )

            resp = self.client.responses.create(
                model="gpt-5",
                input=[
                    {"role": "system", "content": [{"type": "input_text", "text": system_text}]},
                    {"role": "user", "content": [{"type": "input_text", "text": prompt}]},
                ],
                # Some GPT-5 Responses models do not accept 'temperature'. Omit unless required.
                max_output_tokens=1000,
                # Force text output and minimize reasoning to avoid reasoning-only responses
                reasoning={"effort": "low"},  # Minimize reasoning to force actual text output
                text={"format": {"type": "text"}, "verbosity": "high"}  # Force verbose text output
            )

            # Extract text from GPT-5 response
            import logging
            logger = logging.getLogger(__name__)
            
            # Try direct output_text attribute first
            grading_text = getattr(resp, "output_text", "") or ""
            
            # If empty, parse from output items
            if not grading_text and hasattr(resp, "output"):
                parts = []
                for item in resp.output or []:
                    # Handle message items (expected format)
                    if hasattr(item, "type") and item.type == "message":
                        if hasattr(item, "content"):
                            for c in item.content or []:
                                if hasattr(c, "type") and c.type in ("output_text", "text"):
                                    if hasattr(c, "text") and c.text:
                                        parts.append(c.text)
                                elif hasattr(c, "text"):
                                    parts.append(c.text)
                    # Handle reasoning items if they slip through (shouldn't with effort="low")
                    elif hasattr(item, "type") and item.type == "reasoning":
                        logger.warning("[AI_GRADER] Got reasoning item despite effort='low' setting")
                
                grading_text = "\n".join(p for p in parts if p)
            
            # Log the result
            if grading_text:
                logger.debug(f"[AI_GRADER] Extracted text (length={len(grading_text)}): {grading_text[:200]}...")
            else:
                logger.error(f"[AI_GRADER] Failed to extract text from response. Response type: {type(resp)}, has output: {hasattr(resp, 'output')}")
                # Log more details for debugging
                if hasattr(resp, "model_dump"):
                    import json
                    dump = resp.model_dump()
                    logger.error(f"[AI_GRADER] Response structure: {json.dumps(dump, default=str)[:500]}")
            
            return self._parse_grading_response(grading_text)
            
        except Exception as e:
            return GradingResult(
                passed=False,
                reasoning=f"AI grading failed: {str(e)}",
                confidence=0.0
            )
    
    def _build_grading_prompt(
        self,
        test_name: str,
        expected_behavior: str,
        request_data: Dict[str, Any],
        response_data: Dict[str, Any]
    ) -> str:
        """Build the grading prompt for the AI."""
        return f"""Grade this E2E test result:

TEST NAME: {test_name}

EXPECTED BEHAVIOR: {expected_behavior}

REQUEST DATA:
{json.dumps(request_data, indent=2)}

ACTUAL RESPONSE:
{json.dumps(response_data, indent=2)}

GRADING CRITERIA:
1. Does the response fulfill the expected behavior?
2. Consider semantic equivalence (e.g., "duplicate" vs "similar" mean the same)
3. Approval flows (needs_approval=true) are valid successful responses
4. Different response formats are acceptable if they achieve the goal
5. Focus on functionality, not exact wording

IMPORTANT CONTEXT:
- success=true means operation completed
- needs_approval=true means operation needs user confirmation (this is SUCCESS for approval flow tests)
- action_type tells you what kind of approval is needed
- For duplicate detection: both "duplicate" and "similar" indicate success
- For fuzzy matching tests: duplicate detection working correctly = success
- For conflict detection: suggesting alternative times is success
- For task creation: having an ID means success
- For AI routing tests: task-related errors (ambiguity, not found) routed to Reclaim = SUCCESS
- For AI routing tests: event-related errors routed to Nylas = SUCCESS
- The key is correct ROUTING, not successful completion of the operation

Respond with:
VERDICT: PASS or FAIL
CONFIDENCE: 0.0 to 1.0
REASONING: Detailed explanation of your grading decision

Be thorough in your reasoning and explain what you found in the response that supports your verdict."""
    
    def _parse_grading_response(self, grading_text: str) -> GradingResult:
        """Parse the AI's grading response."""
        import logging
        logger = logging.getLogger(__name__)
        
        if not grading_text or not grading_text.strip():
            logger.warning("[AI_GRADER] Empty grading text received")
            return GradingResult(
                passed=False,
                reasoning="AI grader returned empty response - unable to determine verdict",
                confidence=0.0
            )
        
        lines = grading_text.strip().split('\n')
        
        verdict = None
        confidence = 0.0
        reasoning_lines = []
        in_reasoning = False
        
        for line in lines:
            line = line.strip()
            if line.startswith("VERDICT:"):
                verdict = line.replace("VERDICT:", "").strip()
            elif line.startswith("CONFIDENCE:"):
                try:
                    confidence = float(line.replace("CONFIDENCE:", "").strip())
                except:
                    confidence = 0.0
            elif line.startswith("REASONING:"):
                in_reasoning = True
                reasoning_text = line.replace("REASONING:", "").strip()
                if reasoning_text:
                    reasoning_lines.append(reasoning_text)
            elif in_reasoning and line:
                reasoning_lines.append(line)
        
        # Fallbacks when model omits strict headings
        if verdict is None:
            text_lower = grading_text.lower()
            # Try common phrasings
            m = re.search(r"final\s+verdict\s*:\s*(pass|fail)", text_lower)
            if m:
                verdict = m.group(1).upper()
            else:
                m2 = re.search(r"verdict\s+should\s+be\s*(pass|fail)", text_lower)
                if m2:
                    verdict = m2.group(1).upper()
                else:
                    # Look for verdict patterns anywhere in the text
                    if re.search(r'\bPASS\b', grading_text, re.IGNORECASE):
                        verdict = "PASS"
                        confidence = 0.5  # Lower confidence for heuristic match
                    elif re.search(r'\bFAIL\b', grading_text, re.IGNORECASE):
                        verdict = "FAIL"
                        confidence = 0.5  # Lower confidence for heuristic match
                    else:
                        verdict = "FAIL"  # conservative default
                        confidence = 0.0
        
        # Build reasoning from available text
        reasoning = "\n".join(reasoning_lines) if reasoning_lines else ""
        
        # If no structured reasoning found, use the entire response as reasoning
        if not reasoning.strip():
            # Remove the verdict and confidence lines if found
            cleaned_lines = []
            for line in grading_text.split('\n'):
                line_lower = line.lower().strip()
                if not (line_lower.startswith("verdict:") or 
                       line_lower.startswith("confidence:") or
                       line_lower.startswith("reasoning:") and ":" in line):
                    cleaned_lines.append(line.strip())
            reasoning = "\n".join(cleaned_lines).strip()
            
            if not reasoning:
                reasoning = "Unable to parse AI grading reasoning from response: " + grading_text[:200]
        
        logger.debug(f"[AI_GRADER] Parsed verdict={verdict}, confidence={confidence}, reasoning_length={len(reasoning)}")
        
        return GradingResult(
            passed=verdict.upper() == "PASS" if verdict else False,
            reasoning=reasoning,
            confidence=confidence
        )
    
    def print_grading_result(
        self,
        test_name: str,
        expected_behavior: str,
        request_data: Dict[str, Any],
        response_data: Dict[str, Any],
        result: GradingResult
    ):
        """Print a formatted grading result to the terminal and save to log file."""
        # Create the formatted output
        output_lines = []
        output_lines.append("\n" + "=" * 80)
        output_lines.append("🤖 " + "=" * 20 + " AI GRADING RESULT " + "=" * 20 + " 🤖")
        output_lines.append("=" * 80)
        output_lines.append(f"TEST: {test_name}")
        output_lines.append("=" * 80)
        
        # Print to console with color
        print("\n" + "=" * 80)
        print("🤖 " + "=" * 20 + " AI GRADING RESULT " + "=" * 20 + " 🤖")
        print("=" * 80)
        print(f"{Fore.CYAN}TEST: {test_name}{Style.RESET_ALL}")
        print("=" * 80)
        
        # Also save to a dedicated AI grading log file
        log_dir = "logs/e2e/ai_grading"
        os.makedirs(log_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = f"{log_dir}/ai_grading_{timestamp}.log"
        
        with open(log_file, "a") as f:
            f.write("\n".join(output_lines) + "\n")
        
        # Request section
        print(f"\n{Fore.BLUE}📤 REQUEST:{Style.RESET_ALL}")
        if "query" in request_data:
            print(f"   Query: \"{request_data['query']}\"")
        if "context" in request_data:
            print(f"   Context: \"{request_data['context']}\"")
        if request_data.get("approved"):
            print(f"   Action: Approving {request_data.get('action_type', 'unknown action')}")
        
        # Response section
        print(f"\n{Fore.BLUE}📥 RESPONSE:{Style.RESET_ALL}")
        if "action_type" in response_data:
            print(f"   Type: {response_data['action_type']}")
        if "success" in response_data:
            print(f"   Success: {response_data['success']}")
        if "needs_approval" in response_data:
            print(f"   Needs Approval: {response_data['needs_approval']}")
        if "message" in response_data:
            print(f"   Message: \"{response_data['message']}\"")
        elif response_data.get("preview", {}).get("details", {}).get("message"):
            print(f"   Message: \"{response_data['preview']['details']['message']}\"")
        
        # Expected behavior
        print(f"\n{Fore.BLUE}🎯 EXPECTED:{Style.RESET_ALL}")
        print(f"   {expected_behavior}")
        
        # AI Grading section
        print(f"\n{Fore.BLUE}🤖 AI GRADING VERDICT:{Style.RESET_ALL}")
        if result.passed:
            print(f"   {Fore.GREEN}✅ PASS{Style.RESET_ALL} (confidence: {result.confidence:.1%})")
        else:
            print(f"   {Fore.RED}❌ FAIL{Style.RESET_ALL} (confidence: {result.confidence:.1%})")
        
        print(f"\n   {Fore.YELLOW}AI Reasoning:{Style.RESET_ALL}")
        for line in result.reasoning.split('\n'):
            if line.strip():
                print(f"   {line}")
        
        print("\n" + "=" * 80 + "\n")
        
        # Save complete grading to log file
        with open(log_file, "a") as f:
            f.write(f"\nREQUEST:\n")
            if "query" in request_data:
                f.write(f"   Query: \"{request_data['query']}\"\n")
            if "context" in request_data:
                f.write(f"   Context: \"{request_data['context']}\"\n")
            if request_data.get("approved"):
                f.write(f"   Action: Approving {request_data.get('action_type', 'unknown action')}\n")
            
            f.write(f"\nRESPONSE:\n")
            if "action_type" in response_data:
                f.write(f"   Type: {response_data['action_type']}\n")
            if "success" in response_data:
                f.write(f"   Success: {response_data['success']}\n")
            if "needs_approval" in response_data:
                f.write(f"   Needs Approval: {response_data['needs_approval']}\n")
            if "message" in response_data:
                f.write(f"   Message: \"{response_data['message']}\"\n")
            elif response_data.get("preview", {}).get("details", {}).get("message"):
                f.write(f"   Message: \"{response_data['preview']['details']['message']}\"\n")
            
            f.write(f"\nEXPECTED:\n")
            f.write(f"   {expected_behavior}\n")
            
            f.write(f"\nAI GRADING VERDICT:\n")
            if result.passed:
                f.write(f"   ✅ PASS (confidence: {result.confidence:.1%})\n")
            else:
                f.write(f"   ❌ FAIL (confidence: {result.confidence:.1%})\n")
            
            f.write(f"\nAI Reasoning:\n")
            for line in result.reasoning.split('\n'):
                if line.strip():
                    f.write(f"   {line}\n")
            
            f.write("\n" + "=" * 80 + "\n\n")


# Singleton instance
_grader_instance = None

def get_grader() -> AITestGrader:
    """Get or create the singleton AI grader instance."""
    global _grader_instance
    if _grader_instance is None:
        _grader_instance = AITestGrader()
    return _grader_instance


def ai_grade_response(
    test_name: str,
    expected_behavior: str,
    request_data: Dict[str, Any],
    response_data: Dict[str, Any],
    print_result: bool = True
) -> GradingResult:
    """Convenience function to grade a response using AI."""
    grader = get_grader()
    result = grader.grade_response(
        test_name, expected_behavior, request_data, response_data
    )
    
    if print_result:
        grader.print_grading_result(
            test_name, expected_behavior, request_data, response_data, result
        )
    
    return result