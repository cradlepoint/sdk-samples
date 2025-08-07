#!/usr/bin/env python3
"""
Router Data Browser - A web-based file explorer interface for router configuration and status data.
Visualizes JSON data from the CP library as a hierarchical folder/file structure.
"""

import json
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from http import HTTPStatus
from urllib.parse import parse_qs, urlparse
import cp

class RouterDataHandler(SimpleHTTPRequestHandler):
    """Custom HTTP handler for serving the router data browser interface."""
    
    def __init__(self, *args, **kwargs):
        # Set the directory to serve static files from
        script_dir = os.path.dirname(os.path.abspath(__file__))
        super().__init__(*args, directory=script_dir, **kwargs)
    
    def do_GET(self):
        """Handle GET requests for API endpoints and static files."""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/api/tree':
            self.handle_tree_request(parsed_path.query)
        elif parsed_path.path == '/api/data':
            self.handle_data_request(parsed_path.query)
        elif parsed_path.path == '/api/search':
            self.handle_search_request(parsed_path.query)
        elif parsed_path.path == '/api/decrypt':
            self.handle_decrypt_request(parsed_path.query)
        else:
            # Serve static files (HTML, CSS, JS)
            super().do_GET()
    
    def handle_tree_request(self, query):
        """Handle requests for tree structure data."""
        try:
            params = parse_qs(query)
            path = params.get('path', [''])[0]
            
            # Get tree structure for the requested path
            tree_data = get_tree_structure(path)
            
            self.send_json_response(tree_data)
        except Exception as e:
            self.send_error_response(f"Error getting tree data: {str(e)}")
    
    def handle_data_request(self, query):
        """Handle requests for actual data at a specific path."""
        try:
            params = parse_qs(query)
            path = params.get('path', [''])[0]
            
            if not path:
                self.send_error_response("Path parameter required")
                return
            
            # Get actual data from the router
            data = cp.get(path)
            
            response = {
                'path': path,
                'data': data,
                'type': type(data).__name__,
                'size': len(str(data)) if data is not None else 0
            }
            
            self.send_json_response(response)
        except Exception as e:
            self.send_error_response(f"Error getting data: {str(e)}")
    
    def handle_search_request(self, query):
        """Handle search requests."""
        try:
            params = parse_qs(query)
            search_term = params.get('q', [''])[0]
            
            if not search_term:
                self.send_error_response("Search term required")
                return
            
            # Perform search across router data
            results = search_router_data(search_term)
            
            self.send_json_response({'results': results, 'query': search_term})
        except Exception as e:
            self.send_error_response(f"Error searching: {str(e)}")

    def handle_decrypt_request(self, query):
        """Handle decrypt requests for encrypted values."""
        try:
            params = parse_qs(query)
            path = params.get('path', [''])[0]
            
            if not path:
                self.send_error_response('Path parameter required for decryption')
                return
            
            cp.log(f'Decrypting value at path: {path}')
            
            # Use cp.decrypt to decrypt the value at the specified path
            decrypted_result = cp.decrypt(path)
            
            cp.log(f'Decrypt result type: {type(decrypted_result)}, value: {decrypted_result}')
            
            # Handle different response formats
            if decrypted_result is None:
                self.send_error_response(f'Failed to decrypt value at path: {path}')
                return
            
            # Extract the actual decrypted value
            if isinstance(decrypted_result, dict):
                # If it's a dict, try to get the actual value
                decrypted_value = decrypted_result
            elif isinstance(decrypted_result, str):
                # If it's already a string, use it directly
                decrypted_value = decrypted_result
            else:
                # For other types, convert to string
                decrypted_value = str(decrypted_result)
            
            self.send_json_response({
                'decrypted_value': decrypted_value,
                'path': path,
                'original_type': str(type(decrypted_result))
            })
            
        except Exception as e:
            cp.log(f'Error handling decrypt request: {str(e)}')
            self.send_error_response(f'Decryption failed: {str(e)}')
    
    def send_json_response(self, data):
        """Send a JSON response."""
        self.send_response(HTTPStatus.OK)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(bytes(json.dumps(data, indent=2), 'utf-8'))
    
    def send_error_response(self, message):
        """Send an error response."""
        self.send_response(HTTPStatus.INTERNAL_SERVER_ERROR)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        error_data = {'error': message}
        self.wfile.write(bytes(json.dumps(error_data), 'utf-8'))


def get_tree_structure(base_path=''):
    """
    Get the tree structure by calling cp.get() on the specified path.
    
    Args:
        base_path (str): Path to explore (empty string for root)
    
    Returns:
        dict: Tree structure with folders and files from router
    """
    try:
        # For empty path, show the standard top-level folders
        if not base_path:
            tree_items = []
            for folder_name in ['status', 'config', 'control', 'state']:
                tree_items.append({
                    'name': folder_name,
                    'type': 'folder',
                    'path': folder_name,
                    'has_children': True
                })
            return {'tree': tree_items, 'path': ''}
        
        # Get data from router using cp.get()
        data = cp.get(base_path)
        
        if data is None:
            return {'error': f'No data found at path: {base_path}'}
        
        # Build tree structure from the router response
        tree = build_tree_from_data(data, base_path)
        return {'tree': tree, 'path': base_path}
        
    except Exception as e:
        cp.log(f'Error getting tree structure for {base_path}: {str(e)}')
        return {'error': f'Error building tree: {str(e)}'}


def build_tree_from_data(data, current_path):
    """
    Build a tree structure from router data.
    
    Args:
        data: The data returned from cp.get()
        current_path (str): Current path in the router structure
    
    Returns:
        list: Tree items representing the data structure
    """
    tree_items = []
    
    if isinstance(data, dict):
        # For dictionaries, each key becomes a node
        for key, value in data.items():
            item_path = f"{current_path}/{key}".strip('/')
            
            # Determine if this is a folder or file based on the value
            if isinstance(value, dict) and value:
                # Non-empty dict = folder
                tree_items.append({
                    'name': key,
                    'type': 'folder',
                    'path': item_path,
                    'has_children': True
                })
            elif isinstance(value, list) and value:
                # Non-empty list = folder (array of items)
                tree_items.append({
                    'name': key,
                    'type': 'folder',
                    'path': item_path,
                    'has_children': True,
                    'list_type': True  # Mark as list for special handling
                })
            else:
                # Primitive value or empty container = file
                tree_items.append({
                    'name': key,
                    'type': 'file',
                    'path': item_path,
                    'value_type': type(value).__name__,
                    'preview': str(value)[:50] if value is not None else 'null'
                })
    
    elif isinstance(data, list):
        # For lists, create numbered items
        for index, item in enumerate(data):
            item_path = f"{current_path}/{index}".strip('/')
            
            if isinstance(item, (dict, list)) and item:
                # Complex item = folder
                tree_items.append({
                    'name': f"[{index}]",
                    'type': 'folder',
                    'path': item_path,
                    'has_children': True
                })
            else:
                # Simple item = file
                tree_items.append({
                    'name': f"[{index}]",
                    'type': 'file',
                    'path': item_path,
                    'value_type': type(item).__name__,
                    'preview': str(item)[:50] if item is not None else 'null'
                })
    
    else:
        # Single value - shouldn't normally happen at tree level, but handle gracefully
        tree_items.append({
            'name': 'value',
            'type': 'file',
            'path': current_path,
            'value_type': type(data).__name__,
            'preview': str(data)[:50] if data is not None else 'null'
        })
    
    # Sort items: folders first, then files, alphabetically within each group
    tree_items.sort(key=lambda x: (x['type'] == 'file', x['name'].lower()))
    
    return tree_items


def is_data_structure_deep(data, max_depth=3):
    """
    Check if a data structure is deep enough to warrant lazy loading.
    
    Args:
        data: The data to check
        max_depth (int): Maximum depth to check before considering it deep
    
    Returns:
        bool: True if structure is deep
    """
    def check_depth(obj, current_depth=0):
        if current_depth >= max_depth:
            return True
        
        if isinstance(obj, dict):
            return any(check_depth(v, current_depth + 1) for v in obj.values() if isinstance(v, (dict, list)))
        elif isinstance(obj, list):
            return any(check_depth(item, current_depth + 1) for item in obj if isinstance(item, (dict, list)))
        
        return False
    
    return check_depth(data)


def search_router_data(search_term):
    """
    Search through router data for the given term.
    
    Args:
        search_term (str): Term to search for
        
    Returns:
        list: List of matching paths and data
    """
    results = []
    search_term = search_term.lower()
    
    try:
        # Get all router data from root
        root_data = cp.get('')
        if root_data:
            # Search recursively through all data
            results = search_data_recursively(root_data, '', search_term, max_depth=4)
    except Exception as e:
        cp.log(f'Error searching router data: {str(e)}')
        return []
    
    # Sort results by relevance
    def sort_key(item):
        match_type_priority = {'path': 0, 'key': 1, 'content': 2}
        return (match_type_priority.get(item['match_type'], 3), item['path'])
    
    results.sort(key=sort_key)
    return results[:100]


def search_data_recursively(data, current_path, search_term, max_depth=3, current_depth=0):
    """
    Recursively search through data structure for matching paths and content.
    
    Args:
        data: Current data to search
        current_path (str): Current path in the data structure
        search_term (str): Term to search for
        max_depth (int): Maximum recursion depth
        current_depth (int): Current recursion depth
    
    Returns:
        list: Found matches
    """
    matches = []
    
    if current_depth >= max_depth:
        return matches
    
    # Check if current path matches search term
    if search_term in current_path.lower():
        try:
            # Get the actual data at this path for preview
            path_data = cp.get(current_path)
            matches.append({
                'path': current_path,
                'match_type': 'path',
                'preview': str(path_data)[:100] if path_data is not None else 'No data'
            })
        except:
            matches.append({
                'path': current_path,
                'match_type': 'path',
                'preview': 'Error accessing data'
            })
    
    # Search through data content
    if isinstance(data, dict):
        for key, value in data.items():
            item_path = f"{current_path}/{key}".strip('/')
            
            # Check if key matches
            if search_term in key.lower():
                matches.append({
                    'path': item_path,
                    'match_type': 'key',
                    'preview': f"Key: {key}, Value: {str(value)[:80]}" if value is not None else f"Key: {key}"
                })
            
            # Check if value content matches (for simple values)
            if not isinstance(value, (dict, list)) and value is not None:
                if search_term in str(value).lower():
                    matches.append({
                        'path': item_path,
                        'match_type': 'content',
                        'preview': str(value)[:100]
                    })
            
            # Recurse into complex structures
            elif isinstance(value, (dict, list)) and value:
                matches.extend(search_data_recursively(value, item_path, search_term, max_depth, current_depth + 1))
    
    elif isinstance(data, list):
        for index, item in enumerate(data):
            item_path = f"{current_path}/{index}".strip('/')
            
            # Check content of simple items
            if not isinstance(item, (dict, list)) and item is not None:
                if search_term in str(item).lower():
                    matches.append({
                        'path': item_path,
                        'match_type': 'content',
                        'preview': str(item)[:100]
                    })
            
            # Recurse into complex items
            elif isinstance(item, (dict, list)) and item:
                matches.extend(search_data_recursively(item, item_path, search_term, max_depth, current_depth + 1))
    
    return matches





def start_server():
    lan_ip = cp.get('config/lan/0/ip_address')
    server_address = (lan_ip, 9002)
    httpd = HTTPServer(server_address, RouterDataHandler)
    
    cp.log(f'Starting CS Explorer on http://{lan_ip}:9002')
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        cp.log('Stopping CS Explorer')
        httpd.shutdown()


if __name__ == '__main__':
    start_server()
