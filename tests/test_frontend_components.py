"""
Unit tests for frontend components (using React Testing Library would be ideal, but basic structure tests here)
"""
import pytest
import json
import os
import sys

# Note: These are basic structure tests. For full React component testing,
# you would use @testing-library/react and @testing-library/jest-dom


def test_api_service_functions_exist():
    """Test that API service functions are properly defined"""
    # This is a basic check - in real React testing, we'd import and test the functions
    api_file = "frontend/src/services/api.ts"
    assert os.path.exists(api_file), "API service file should exist"
    
    with open(api_file, 'r', encoding='utf-8') as f:
        content = f.read()
        assert "getBlogSources" in content, "getBlogSources function should exist"
        assert "ingestBlog" in content, "ingestBlog function should exist"
        assert "refreshBlog" in content, "refreshBlog function should exist"
        assert "streamAgentResponse" in content, "streamAgentResponse function should exist"


def test_api_service_no_debug_code():
    """Test that API service doesn't contain debug logging code"""
    api_file = "frontend/src/services/api.ts"
    
    with open(api_file, 'r', encoding='utf-8') as f:
        content = f.read()
        assert "#region agent log" not in content, "Debug logging code should be removed"
        assert "127.0.0.1:7253" not in content, "Debug endpoint should be removed"


def test_component_files_exist():
    """Test that all required component files exist"""
    components = [
        "frontend/src/components/Sidebar.tsx",
        "frontend/src/components/Header.tsx",
        "frontend/src/components/Dashboard.tsx",
        "frontend/src/components/BlogManager.tsx",
        "frontend/src/components/BlogIngestModal.tsx",
        "frontend/src/components/ChatInterface.tsx",
        "frontend/src/components/MessageList.tsx",
        "frontend/src/components/InputBox.tsx",
    ]
    
    for component in components:
        assert os.path.exists(component), f"Component {component} should exist"


def test_app_uses_sidebar():
    """Test that App.tsx uses the Sidebar component"""
    app_file = "frontend/src/App.tsx"
    
    with open(app_file, 'r', encoding='utf-8') as f:
        content = f.read()
        assert "Sidebar" in content, "App should use Sidebar component"
        assert "Dashboard" in content, "App should use Dashboard component"
        assert "BlogManager" in content, "App should use BlogManager component"
