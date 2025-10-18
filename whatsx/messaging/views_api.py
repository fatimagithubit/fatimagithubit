from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import requests
import json

# In a production environment, this should be loaded from Django's settings.py
NODE_SERVICE_URL = "http://127.0.0.1:3001/api/v1/whatsapp"

def make_node_request(method, endpoint, data=None):
    """
    A centralized helper function to handle all requests to the Node.js service.
    This improves code reusability and error handling.
    """
    try:
        url = f"{NODE_SERVICE_URL}/{endpoint}"

        # Set appropriate timeouts: longer for starting, shorter for status checks.
        timeout = 20 if endpoint == 'start' else 10

        if method.lower() == 'post':
            response = requests.post(url, json=data, timeout=timeout)
        else:
            response = requests.get(url, timeout=timeout)

        # Raise an HTTPError for bad responses (4xx or 5xx), which will be caught below.
        response.raise_for_status()

        # If the request was successful, return the JSON response from the Node service.
        return JsonResponse(response.json(), status=response.status_code)

    except requests.exceptions.Timeout:
        return JsonResponse({'status': 'ERROR', 'message': 'The connection to the WhatsApp service timed out. It might be busy or starting up.'}, status=504)
    except requests.exceptions.ConnectionError:
        return JsonResponse({'status': 'ERROR', 'message': 'Could not connect to the WhatsApp service. Please ensure the Node.js server is running and accessible.'}, status=503)
    except requests.exceptions.RequestException as e:
        # This block catches all other request-related errors, including the 4xx/5xx errors.
        if e.response is not None:
            try:
                # Try to forward the specific error message from the Node service.
                return JsonResponse(e.response.json(), status=e.response.status_code)
            except json.JSONDecodeError:
                # If the error response isn't valid JSON, return a generic error.
                return JsonResponse({'status': 'ERROR', 'message': 'Received an invalid or non-JSON error response from the service.'}, status=500)

        return JsonResponse({'status': 'ERROR', 'message': f'An unknown API request error occurred: {e}'}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def start_whatsapp_session(request):
    """
    Proxies the 'start session' request from the frontend to the Node.js service.
    """
    return make_node_request('post', 'start')

@csrf_exempt
@require_http_methods(["GET"])
def check_whatsapp_status(request):
    """
    Proxies the 'check status' request from the frontend to the Node.js service.
    """
    return make_node_request('get', 'status')

@csrf_exempt
@require_http_methods(["POST"])
def disconnect_whatsapp_session(request):
    """
    Proxies the 'disconnect session' request from the frontend to the Node.js service.
    """
    return make_node_request('post', 'disconnect')