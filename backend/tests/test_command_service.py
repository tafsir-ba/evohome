"""
Test Agent Command Service - Phase 2 Implementation

Tests:
- POST /api/command/interpret - Converts input to structured plan
- POST /api/command/draft - Creates draft from plan
- POST /api/command/execute - Executes confirmed draft
- GET /api/command/tools - Returns list of tools
- GET /api/command/drafts - Lists user's drafts
- GET /api/command/logs - Gets execution logs
- Intent classification accuracy
- Field extraction accuracy
- Full draft-first flow
"""

import pytest
import requests
import os
import json
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials from problem statement
TEST_AGENT_EMAIL = "demo.agent@upgradeflow.com"
TEST_AGENT_PASSWORD = "demo123"


class TestSetup:
    """Setup fixtures for command service tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for demo agent"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={
                "email": TEST_AGENT_EMAIL,
                "password": TEST_AGENT_PASSWORD
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get("token")
        
        pytest.skip("Authentication failed - cannot run tests")
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Get headers with authentication (for JSON endpoints)"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
    
    @pytest.fixture(scope="class")
    def auth_headers_form(self, auth_token):
        """Get headers with authentication (for form data endpoints)"""
        return {
            "Authorization": f"Bearer {auth_token}"
            # No Content-Type for form data - requests will set it
        }
    
    @pytest.fixture(scope="class")
    def demo_data(self, auth_headers):
        """Get demo project and client data for context"""
        # Get projects
        projects_res = requests.get(
            f"{BASE_URL}/api/projects",
            headers=auth_headers
        )
        projects = projects_res.json() if projects_res.ok else []
        
        # Get clients
        clients_res = requests.get(
            f"{BASE_URL}/api/clients",
            headers=auth_headers
        )
        clients = clients_res.json() if clients_res.ok else []
        
        return {
            "project_id": projects[0]["project_id"] if projects else None,
            "project_name": projects[0]["name"] if projects else None,
            "client_id": clients[0]["client_id"] if clients else None,
            "client_name": clients[0]["name"] if clients else None
        }


class TestCommandTools(TestSetup):
    """Test GET /api/command/tools endpoint"""
    
    def test_tools_endpoint_returns_200(self, auth_headers):
        """Test that tools endpoint is accessible"""
        response = requests.get(
            f"{BASE_URL}/api/command/tools",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/command/tools returns 200")
    
    def test_tools_returns_three_tools(self, auth_headers):
        """Test that exactly 3 tools are returned"""
        response = requests.get(
            f"{BASE_URL}/api/command/tools",
            headers=auth_headers
        )
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        assert len(data) == 3, f"Expected 3 tools, got {len(data)}"
        print(f"✓ Tools endpoint returns {len(data)} tools")
    
    def test_tools_include_expected_intents(self, auth_headers):
        """Test that expected tool intents are present"""
        response = requests.get(
            f"{BASE_URL}/api/command/tools",
            headers=auth_headers
        )
        
        data = response.json()
        intents = [t["intent"] for t in data]
        
        assert "create_quote" in intents, "Missing create_quote tool"
        assert "create_invoice" in intents, "Missing create_invoice tool"
        assert "create_message" in intents, "Missing create_message tool"
        print(f"✓ All expected intents present: {intents}")
    
    def test_tool_structure(self, auth_headers):
        """Test that each tool has required fields"""
        response = requests.get(
            f"{BASE_URL}/api/command/tools",
            headers=auth_headers
        )
        
        data = response.json()
        
        for tool in data:
            assert "intent" in tool, "Tool missing 'intent'"
            assert "name" in tool, "Tool missing 'name'"
            assert "description" in tool, "Tool missing 'description'"
            assert "required_fields" in tool, "Tool missing 'required_fields'"
            assert "optional_fields" in tool, "Tool missing 'optional_fields'"
            print(f"✓ Tool '{tool['name']}' has valid structure")


class TestCommandInterpret(TestSetup):
    """Test POST /api/command/interpret endpoint"""
    
    def test_interpret_invoice_command(self, auth_headers_form, demo_data):
        """Test interpreting 'create invoice' command"""
        response = requests.post(
            f"{BASE_URL}/api/command/interpret",
            headers=auth_headers_form,
            data={
                "command": "Create invoice for kitchen renovation 5000 CHF",
                "context": json.dumps({
                    "project_id": demo_data["project_id"],
                    "client_id": demo_data["client_id"]
                })
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["intent"] == "create_invoice", f"Expected create_invoice intent, got {data['intent']}"
        assert data["intent_confidence"] >= 0.8, f"Confidence too low: {data['intent_confidence']}"
        print(f"✓ 'Create invoice' interpreted as: {data['intent']} (confidence: {data['intent_confidence']})")
    
    def test_interpret_quote_command(self, auth_headers_form, demo_data):
        """Test interpreting 'make a quote' command"""
        response = requests.post(
            f"{BASE_URL}/api/command/interpret",
            headers=auth_headers_form,
            data={
                "command": "Make a quote for bathroom renovation 8500 CHF",
                "context": json.dumps({
                    "project_id": demo_data["project_id"],
                    "client_id": demo_data["client_id"]
                })
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["intent"] == "create_quote", f"Expected create_quote intent, got {data['intent']}"
        print(f"✓ 'Make a quote' interpreted as: {data['intent']} (confidence: {data['intent_confidence']})")
    
    def test_interpret_message_command(self, auth_headers_form, demo_data):
        """Test interpreting 'send message' command"""
        response = requests.post(
            f"{BASE_URL}/api/command/interpret",
            headers=auth_headers_form,
            data={
                "command": "Send message saying Work is complete",
                "context": json.dumps({
                    "project_id": demo_data["project_id"],
                    "client_id": demo_data["client_id"]
                })
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data["intent"] == "create_message", f"Expected create_message intent, got {data['intent']}"
        print(f"✓ 'Send message' interpreted as: {data['intent']} (confidence: {data['intent_confidence']})")
    
    def test_amount_extraction(self, auth_headers_form, demo_data):
        """Test that amount is extracted correctly from command"""
        response = requests.post(
            f"{BASE_URL}/api/command/interpret",
            headers=auth_headers_form,
            data={
                "command": "Create invoice 15000 CHF for plumbing work",
                "context": json.dumps({
                    "project_id": demo_data["project_id"],
                    "client_id": demo_data["client_id"]
                })
            }
        )
        
        assert response.status_code == 200
        
        data = response.json()
        
        # Check fields for amount extraction
        fields = data.get("fields", [])
        amount_field = next((f for f in fields if f["name"] == "amount"), None)
        
        assert amount_field is not None, "Amount not extracted"
        assert amount_field["value"] == 15000.0, f"Expected 15000.0, got {amount_field['value']}"
        assert amount_field["source"] == "user_input", f"Expected user_input source, got {amount_field['source']}"
        print(f"✓ Amount extracted correctly: {amount_field['value']} CHF (source: {amount_field['source']})")
    
    def test_plan_structure(self, auth_headers_form, demo_data):
        """Test that plan has all required fields"""
        response = requests.post(
            f"{BASE_URL}/api/command/interpret",
            headers=auth_headers_form,
            data={
                "command": "Create quote for testing",
                "context": json.dumps({
                    "project_id": demo_data["project_id"],
                    "client_id": demo_data["client_id"]
                })
            }
        )
        
        assert response.status_code == 200
        
        data = response.json()
        
        # Check required plan fields
        assert "plan_id" in data, "Missing plan_id"
        assert "intent" in data, "Missing intent"
        assert "intent_confidence" in data, "Missing intent_confidence"
        assert "fields" in data, "Missing fields"
        assert "missing_fields" in data, "Missing missing_fields"
        assert "is_valid" in data, "Missing is_valid"
        assert "can_execute" in data, "Missing can_execute"
        assert "interpretation_log" in data, "Missing interpretation_log"
        
        print(f"✓ Plan has all required fields: plan_id={data['plan_id'][:20]}...")
    
    def test_missing_required_fields_reported(self, auth_headers_form):
        """Test that missing required fields are reported"""
        # No context provided - should report missing project_id and client_id
        response = requests.post(
            f"{BASE_URL}/api/command/interpret",
            headers=auth_headers_form,
            data={
                "command": "Create invoice for testing",
                "context": "{}"
            }
        )
        
        assert response.status_code == 200
        
        data = response.json()
        
        missing = data.get("missing_fields", [])
        assert len(missing) > 0, "Should report missing fields"
        
        missing_names = [f["name"] for f in missing]
        assert "project_id" in missing_names or "client_id" in missing_names, \
            f"Expected project_id or client_id in missing fields: {missing_names}"
        
        # Check can_execute should be False
        assert data["can_execute"] == False, "can_execute should be False when required fields missing"
        
        print(f"✓ Missing fields correctly reported: {missing_names}")


class TestCommandDraft(TestSetup):
    """Test POST /api/command/draft endpoint"""
    
    def test_create_draft_from_valid_plan(self, auth_headers, auth_headers_form, demo_data):
        """Test creating a draft from a valid plan"""
        # First, interpret a command
        interpret_res = requests.post(
            f"{BASE_URL}/api/command/interpret",
            headers=auth_headers_form,
            data={
                "command": "Create quote for test draft 1000 CHF",
                "context": json.dumps({
                    "project_id": demo_data["project_id"],
                    "client_id": demo_data["client_id"]
                })
            }
        )
        
        assert interpret_res.status_code == 200
        plan = interpret_res.json()
        
        # Create draft
        draft_res = requests.post(
            f"{BASE_URL}/api/command/draft",
            headers=auth_headers,
            json=plan
        )
        
        assert draft_res.status_code == 200, f"Draft creation failed: {draft_res.text}"
        
        draft = draft_res.json()
        assert "draft_id" in draft, "Missing draft_id"
        assert "plan_id" in draft, "Missing plan_id"
        assert draft["status"] == "pending", f"Expected pending status, got {draft['status']}"
        assert draft["intent"] == "create_quote", f"Expected create_quote intent, got {draft['intent']}"
        
        print(f"✓ Draft created: {draft['draft_id']} (status: {draft['status']})")
        
        return draft
    
    def test_draft_has_correct_data(self, auth_headers, auth_headers_form, demo_data):
        """Test that draft contains correct data from plan"""
        # Interpret
        interpret_res = requests.post(
            f"{BASE_URL}/api/command/interpret",
            headers=auth_headers_form,
            data={
                "command": "Create invoice for electrical work 2500 CHF",
                "context": json.dumps({
                    "project_id": demo_data["project_id"],
                    "client_id": demo_data["client_id"]
                })
            }
        )
        
        plan = interpret_res.json()
        
        # Create draft
        draft_res = requests.post(
            f"{BASE_URL}/api/command/draft",
            headers=auth_headers,
            json=plan
        )
        
        draft = draft_res.json()
        
        # Check draft_data structure
        assert "draft_data" in draft, "Missing draft_data"
        draft_data = draft["draft_data"]
        
        assert draft_data.get("document_type") == "invoice", "Wrong document type"
        assert draft_data.get("project_id") == demo_data["project_id"], "Wrong project_id"
        assert draft_data.get("client_id") == demo_data["client_id"], "Wrong client_id"
        
        print(f"✓ Draft data correct: type={draft_data['document_type']}, amount={draft_data.get('total_amount')}")


class TestCommandExecute(TestSetup):
    """Test POST /api/command/execute endpoint"""
    
    def test_execute_quote_draft(self, auth_headers, auth_headers_form, demo_data):
        """Test executing a quote draft creates actual document"""
        # Step 1: Interpret
        interpret_res = requests.post(
            f"{BASE_URL}/api/command/interpret",
            headers=auth_headers_form,
            data={
                "command": "Create quote for TEST_EXEC roof repair 5500 CHF",
                "context": json.dumps({
                    "project_id": demo_data["project_id"],
                    "client_id": demo_data["client_id"]
                })
            }
        )
        
        assert interpret_res.status_code == 200
        plan = interpret_res.json()
        
        # Step 2: Create draft
        draft_res = requests.post(
            f"{BASE_URL}/api/command/draft",
            headers=auth_headers,
            json=plan
        )
        
        assert draft_res.status_code == 200
        draft = draft_res.json()
        
        # Step 3: Execute
        exec_res = requests.post(
            f"{BASE_URL}/api/command/execute",
            headers=auth_headers,
            json={
                "draft_id": draft["draft_id"],
                "confirmed": True
            }
        )
        
        assert exec_res.status_code == 200, f"Execution failed: {exec_res.text}"
        
        result = exec_res.json()
        assert result["status"] == "executed", f"Expected executed status, got {result['status']}"
        assert "result" in result, "Missing result"
        assert result["result"]["type"] == "quote", f"Expected quote type, got {result['result']['type']}"
        assert "id" in result["result"], "Missing document id"
        
        print(f"✓ Quote draft executed: {result['result']['id']}")
        
        return result
    
    def test_execute_invoice_draft(self, auth_headers, auth_headers_form, demo_data):
        """Test executing an invoice draft creates actual document"""
        # Step 1: Interpret
        interpret_res = requests.post(
            f"{BASE_URL}/api/command/interpret",
            headers=auth_headers_form,
            data={
                "command": "Create invoice for TEST_EXEC painting 3000 CHF",
                "context": json.dumps({
                    "project_id": demo_data["project_id"],
                    "client_id": demo_data["client_id"]
                })
            }
        )
        
        plan = interpret_res.json()
        
        # Step 2: Create draft
        draft_res = requests.post(
            f"{BASE_URL}/api/command/draft",
            headers=auth_headers,
            json=plan
        )
        
        draft = draft_res.json()
        
        # Step 3: Execute
        exec_res = requests.post(
            f"{BASE_URL}/api/command/execute",
            headers=auth_headers,
            json={
                "draft_id": draft["draft_id"],
                "confirmed": True
            }
        )
        
        assert exec_res.status_code == 200
        
        result = exec_res.json()
        assert result["status"] == "executed"
        assert result["result"]["type"] == "invoice"
        
        print(f"✓ Invoice draft executed: {result['result']['id']}")
    
    def test_execute_message_draft(self, auth_headers, auth_headers_form, demo_data):
        """Test executing a message draft creates feed activity"""
        # Step 1: Interpret
        interpret_res = requests.post(
            f"{BASE_URL}/api/command/interpret",
            headers=auth_headers_form,
            data={
                "command": "Send message saying TEST_EXEC Work has been completed successfully",
                "context": json.dumps({
                    "project_id": demo_data["project_id"],
                    "client_id": demo_data["client_id"]
                })
            }
        )
        
        plan = interpret_res.json()
        
        # Step 2: Create draft  
        draft_res = requests.post(
            f"{BASE_URL}/api/command/draft",
            headers=auth_headers,
            json=plan
        )
        
        draft = draft_res.json()
        
        # Step 3: Execute
        exec_res = requests.post(
            f"{BASE_URL}/api/command/execute",
            headers=auth_headers,
            json={
                "draft_id": draft["draft_id"],
                "confirmed": True
            }
        )
        
        assert exec_res.status_code == 200
        
        result = exec_res.json()
        assert result["status"] == "executed"
        assert result["result"]["type"] == "message"
        
        print(f"✓ Message draft executed: {result['result']['id']}")
    
    def test_cancel_draft(self, auth_headers, auth_headers_form, demo_data):
        """Test cancelling a draft"""
        # Interpret and create draft
        interpret_res = requests.post(
            f"{BASE_URL}/api/command/interpret",
            headers=auth_headers_form,
            data={
                "command": "Create quote for TEST_CANCEL 1000 CHF",
                "context": json.dumps({
                    "project_id": demo_data["project_id"],
                    "client_id": demo_data["client_id"]
                })
            }
        )
        
        plan = interpret_res.json()
        
        draft_res = requests.post(
            f"{BASE_URL}/api/command/draft",
            headers=auth_headers,
            json=plan
        )
        
        draft = draft_res.json()
        
        # Cancel the draft
        cancel_res = requests.post(
            f"{BASE_URL}/api/command/execute",
            headers=auth_headers,
            json={
                "draft_id": draft["draft_id"],
                "confirmed": False
            }
        )
        
        assert cancel_res.status_code == 200
        
        result = cancel_res.json()
        assert result["status"] == "cancelled"
        
        print(f"✓ Draft cancelled: {draft['draft_id']}")


class TestCommandDraftsAndLogs(TestSetup):
    """Test GET /api/command/drafts and /api/command/logs endpoints"""
    
    def test_list_drafts(self, auth_headers):
        """Test listing user's drafts"""
        response = requests.get(
            f"{BASE_URL}/api/command/drafts",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list), "Drafts should be a list"
        
        print(f"✓ Listed {len(data)} drafts")
    
    def test_list_drafts_by_status(self, auth_headers):
        """Test filtering drafts by status"""
        response = requests.get(
            f"{BASE_URL}/api/command/drafts?status=executed",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        
        data = response.json()
        for draft in data:
            assert draft["status"] == "executed", f"Expected executed status, got {draft['status']}"
        
        print(f"✓ Filtered {len(data)} executed drafts")
    
    def test_get_command_logs(self, auth_headers):
        """Test getting command execution logs"""
        response = requests.get(
            f"{BASE_URL}/api/command/logs",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list), "Logs should be a list"
        
        print(f"✓ Retrieved {len(data)} command logs")


class TestIntentClassification(TestSetup):
    """Test intent classification accuracy"""
    
    def test_invoice_variations(self, auth_headers_form, demo_data):
        """Test various invoice command phrasings"""
        commands = [
            "create invoice",
            "make an invoice",
            "new invoice",
            "generate bill",
            "facture for client"  # French variant
        ]
        
        for cmd in commands:
            response = requests.post(
                f"{BASE_URL}/api/command/interpret",
                headers=auth_headers_form,
                data={
                    "command": cmd,
                    "context": json.dumps({"project_id": demo_data["project_id"]})
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                assert data["intent"] == "create_invoice", f"'{cmd}' should be create_invoice, got {data['intent']}"
                print(f"  ✓ '{cmd}' -> create_invoice")
    
    def test_quote_variations(self, auth_headers_form, demo_data):
        """Test various quote command phrasings"""
        commands = [
            "create quote",
            "make a quote",
            "new estimate",
            "generate quote",
            "devis for bathroom"  # French variant
        ]
        
        for cmd in commands:
            response = requests.post(
                f"{BASE_URL}/api/command/interpret",
                headers=auth_headers_form,
                data={
                    "command": cmd,
                    "context": json.dumps({"project_id": demo_data["project_id"]})
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                assert data["intent"] == "create_quote", f"'{cmd}' should be create_quote, got {data['intent']}"
                print(f"  ✓ '{cmd}' -> create_quote")
    
    def test_message_variations(self, auth_headers_form, demo_data):
        """Test various message command phrasings"""
        commands = [
            "send message",
            "post update",
            "message saying hello"
        ]
        
        for cmd in commands:
            response = requests.post(
                f"{BASE_URL}/api/command/interpret",
                headers=auth_headers_form,
                data={
                    "command": cmd,
                    "context": json.dumps({"project_id": demo_data["project_id"]})
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                assert data["intent"] == "create_message", f"'{cmd}' should be create_message, got {data['intent']}"
                print(f"  ✓ '{cmd}' -> create_message")


class TestFullFlow(TestSetup):
    """Test complete interpret -> draft -> execute flow"""
    
    def test_full_quote_flow(self, auth_headers, auth_headers_form, demo_data):
        """Test complete flow for creating a quote"""
        print("\n=== Full Quote Flow Test ===")
        
        # Step 1: Interpret
        print("Step 1: Interpreting command...")
        interpret_res = requests.post(
            f"{BASE_URL}/api/command/interpret",
            headers=auth_headers_form,
            data={
                "command": "Create quote for TEST_FULLFLOW bathroom tiles 8500 CHF",
                "context": json.dumps({
                    "project_id": demo_data["project_id"],
                    "client_id": demo_data["client_id"]
                })
            }
        )
        
        assert interpret_res.status_code == 200
        plan = interpret_res.json()
        
        print(f"  Intent: {plan['intent']}")
        print(f"  Confidence: {plan['intent_confidence']}")
        print(f"  Can Execute: {plan['can_execute']}")
        print(f"  Fields: {len(plan['fields'])}")
        print(f"  Missing Fields: {len(plan['missing_fields'])}")
        
        # Step 2: Create draft
        print("\nStep 2: Creating draft...")
        draft_res = requests.post(
            f"{BASE_URL}/api/command/draft",
            headers=auth_headers,
            json=plan
        )
        
        assert draft_res.status_code == 200
        draft = draft_res.json()
        
        print(f"  Draft ID: {draft['draft_id']}")
        print(f"  Status: {draft['status']}")
        
        # Step 3: Execute
        print("\nStep 3: Executing draft...")
        exec_res = requests.post(
            f"{BASE_URL}/api/command/execute",
            headers=auth_headers,
            json={
                "draft_id": draft["draft_id"],
                "confirmed": True
            }
        )
        
        assert exec_res.status_code == 200
        result = exec_res.json()
        
        print(f"  Status: {result['status']}")
        print(f"  Document Type: {result['result']['type']}")
        print(f"  Document ID: {result['result']['id']}")
        
        # Verify document was created
        print("\nStep 4: Verifying document exists...")
        doc_res = requests.get(
            f"{BASE_URL}/api/documents/{result['result']['id']}",
            headers=auth_headers
        )
        
        assert doc_res.status_code == 200, f"Document not found: {doc_res.status_code}"
        doc = doc_res.json()
        
        print(f"  Document Number: {doc.get('document_number')}")
        print(f"  Total Amount: {doc.get('total_amount')}")
        print(f"  Status: {doc.get('status')}")
        
        print("\n✓ Full flow completed successfully!")


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
