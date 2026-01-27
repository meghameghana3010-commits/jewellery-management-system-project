import os
import json
import uuid
from datetime import datetime, UTC
from flask import Flask, render_template, jsonify, request, redirect, url_for, abort, session
from dotenv import load_dotenv
import random
# Optional email/SMS libs
try:
    from flask_mail import Mail, Message
except Exception:
    Mail = None
    Message = None

try:
    from twilio.rest import Client as TwilioClient
except Exception:
    TwilioClient 

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret")
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "")

# Load products once
PRODUCTS_PATH = os.path.join(os.path.dirname(__file__), 'products.json')

# Safely load products JSON without crashing the app
if os.path.exists(PRODUCTS_PATH) and os.path.getsize(PRODUCTS_PATH) > 0:
    try:
        with open(PRODUCTS_PATH, 'r', encoding='utf-8') as f:
            PRODUCTS = json.load(f)
    except json.JSONDecodeError as e:
        # Log the error and fall back to an empty list so the app keeps running
        print(f"Failed to parse products.json: {e}")
        PRODUCTS = []
else:
    # File missing or empty: default to an empty products list
    PRODUCTS = []

# In-memory order store (demo)
ORDERS = {}

# Email setup (optional)
mail = None
if Mail:
    app.config.update(
        MAIL_SERVER=os.getenv('MAIL_SERVER'),
        MAIL_PORT=int(os.getenv('MAIL_PORT', '587')),
        MAIL_USE_TLS=os.getenv('MAIL_USE_TLS', 'true').lower() == 'true',
        MAIL_USERNAME=os.getenv('MAIL_USERNAME'),
        MAIL_PASSWORD=os.getenv('MAIL_PASSWORD'),
        MAIL_DEFAULT_SENDER=os.getenv('MAIL_DEFAULT_SENDER')
    )
    try:
        mail = Mail(app)
    except Exception:
        mail = None

# SMS setup (optional)
twilio_client = None
if TwilioClient and os.getenv('TWILIO_ACCOUNT_SID') and os.getenv('TWILIO_AUTH_TOKEN'):
    try:
        twilio_client = TwilioClient(os.getenv('TWILIO_ACCOUNT_SID'), os.getenv('TWILIO_AUTH_TOKEN'))
    except Exception:
        twilio_client = None


def send_email(to_email: str, subject: str, body: str):
    if not mail or not Message:
        return False
    try:
        msg = Message(subject=subject, recipients=[to_email], body=body)
        mail.send(msg)
        return True
    except Exception:
        return False


def send_sms(to_number: str, message: str):
    if not twilio_client or not os.getenv('TWILIO_FROM_NUMBER'):
        return False
    try:
        twilio_client.messages.create(
            body=message,
            from_=os.getenv('TWILIO_FROM_NUMBER'),
            to=to_number
        )
        return True
    except Exception:
        return False


@app.route('/')
def home():
    if not session.get('user'):
        return redirect(url_for('login'))
    return render_template('index.html', products=PRODUCTS, user=session.get('user'))


@app.route('/login')
def login():
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))


@app.route('/api/products')
def api_products():
    return jsonify(PRODUCTS)


@app.route('/api/send-otp', methods=['POST'])
def api_send_otp():
    phone = request.json.get('phone')
    if not phone or not phone.isdigit() or len(phone) != 10:
        return jsonify({'error': 'Invalid phone number'}), 400

    # Generate and store a mock OTP
    otp = str(random.randint(100000, 999999))
    session['otp'] = otp
    session['otp_phone'] = phone

    # In a real app, you would send this OTP via SMS
    # For this demo, we'll return it in the response
    return jsonify({'mock_otp': otp})


@app.route('/api/verify-otp', methods=['POST'])
def api_verify_otp():
    phone = request.json.get('phone')
    otp = request.json.get('otp')

    if not all([phone, otp, session.get('otp'), session.get('otp_phone')]) or \
       phone != session['otp_phone'] or \
       otp != session['otp']:
        return jsonify({'error': 'Invalid OTP'}), 400

    # OTP is correct, log the user in
    session['user'] = {'phone': phone}
    session.pop('otp', None)
    session.pop('otp_phone', None)

    return jsonify({'message': 'Login successful'})


@app.route('/api/order', methods=['POST'])
def api_create_order():
    data = request.get_json(force=True)
    name = data.get('name')
    email = data.get('email')
    phone = data.get('phone')
    address = data.get('address')
    items = data.get('items', [])

    order_id = uuid.uuid4().hex[:10].upper()
    ORDERS[order_id] = {
        'id': order_id,
        'name': name,
        'email': email,
        'phone': phone,
        'address': address,
        'items': items,
        'status': 'Confirmed',
        'created_at': datetime.now(UTC).isoformat()
    }

    # Notify (best-effort, optional)
    try:
        if email:
            send_email(email, f"Order {order_id} Confirmed", f"Thank you {name}! Your order {order_id} is confirmed.")
    except Exception:
        pass
    try:
        if phone:
            send_sms(phone, f"Order {order_id} confirmed. Thank you for shopping with us!")
    except Exception:
        pass

    return jsonify({
        'order_id': order_id,
        'track_url': url_for('track', order_id=order_id)
    }), 201


@app.route('/order/<order_id>')
def order_confirmed(order_id):
    order = ORDERS.get(order_id)
    if not order:
        return redirect(url_for('home'))
    return render_template('order_confirmed.html', order=order)


@app.route('/track')
def track():
    order_id = request.args.get('order_id')
    return render_template('track.html', order_id=order_id)


@app.route('/api/order/<order_id>/status')
def api_order_status(order_id):
    order = ORDERS.get(order_id)
    if not order:
        return jsonify({'error': 'not found'}), 404
    return jsonify({'order_id': order_id, 'status': order['status']})


@app.route('/api/order/<order_id>/mark_delivered', methods=['POST'])
def api_mark_delivered(order_id):
    order = ORDERS.get(order_id)
    if not order:
        return jsonify({'error': 'not found'}), 404
    order['status'] = 'Delivered'
    return jsonify({'ok': True, 'status': order['status']})


@app.route('/api/unsplash')
def api_unsplash():
    """Proxy to Unsplash Search API to fetch one image URL for a query.
    Query params:
      q: search text (e.g., 'gold ring jewelry')
    """
    q = (request.args.get('q') or '').strip()
    if not q:
        return jsonify({'error': 'missing q'}), 400
    
    # Define reliable fallback URLs
    fallback_urls = [
        f'https://via.placeholder.com/500x500/1e2640/aab2c8?text={q.split()[0] if q.split() else "Item"}',
        f'https://picsum.photos/500/500?random={hash(q) % 1000}',
        f'https://source.unsplash.com/500x500/?jewelry,{q.replace(" ", ",")}'
    ]
    
    # If no key, use fallback
    if not UNSPLASH_ACCESS_KEY:
        return jsonify({'url': fallback_urls[2]})
    
    try:
        import requests
        r = requests.get(
            'https://api.unsplash.com/search/photos',
            params={'query': f'{q} jewelry', 'per_page': 3, 'orientation': 'squarish'},
            headers={'Authorization': f'Client-ID {UNSPLASH_ACCESS_KEY}'},
            timeout=5
        )
        if r.status_code != 200:
            return jsonify({'url': fallback_urls[2]})
        
        data = r.json()
        results = data.get('results') or []
        if not results:
            return jsonify({'url': fallback_urls[2]})
        
        # Try to get the best quality URL
        for result in results:
            urls = result.get('urls') or {}
            url = urls.get('small') or urls.get('regular') or urls.get('thumb')
            if url:
                return jsonify({'url': url})
        
        return jsonify({'url': fallback_urls[2]})
    except Exception as e:
        print(f"Unsplash API error: {e}")
        return jsonify({'url': fallback_urls[0]})


@app.route('/try-on')
def try_on():
    return render_template('try_on.html')


@app.route('/api/chat', methods=['POST'])
def api_chat():
    """AI-powered chatbot API using Gemini for jewelry assistance."""
    data = request.get_json(force=True)
    user_message = (data.get('message') or '').strip().lower()
    
    if not user_message:
        return jsonify({'reply': 'Please ask me something about our jewelry collection!'})
    
    # Try Gemini first
    try:
        from google import genai
        client = genai.Client()
        
        system_prompt = f"""You are a helpful AI assistant for "Shri Jewellery", a premium jewelry store in India. Here's important information about the store:

STORE INFORMATION:
- Name: Shri Jewellery
- Location: Chinya, Nagamangala Taluk, Mandya District, Mysore Main Road
- Phone: +91 90192 31931 / +91 89044 39579
- We specialize in Gold, Silver, and Diamond jewelry for Women, Men, and Children

PRODUCT CATALOG:
- Gold Jewelry: Rings (5g-20g), Chains (10g-35g), Necklaces (10g-30g), Nose pins (1g-3g)
- Silver Jewelry: Rings (5g-10g), Chains (10g-20g), Necklaces (5g-10g), Nose pins (1g-2g)
- Diamond Jewelry: Rings (5g-10g), Necklaces (10g-20g), Nose pins (1g-2g)
- Children's Collection: Gold rings (2g-5g), Silver rings (2g-5g), Gold chains (5g-10g), Silver chains (5g-10g)

PRICING (Base prices, calculated per gram):
- Gold: Starting from ₹6,500 for children's items, up to ₹144,000 for heavy chains
- Silver: Starting from ₹240 for nose pins, up to ₹6,000 for chains
- Diamond: Starting from ₹1,960 for nose pins, up to ₹250,000 for necklaces

SERVICES:
- Online ordering with order tracking
- Delivery across India (3-7 business days)
- Virtual try-on feature available
- 7-day return/exchange policy

User's question: {user_message}
Provide a helpful, accurate response as Shri Jewellery's AI assistant:"""
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=system_prompt
        )
        
        reply = response.text.strip() if response.text else None
        if reply:
            if len(reply) > 800:
                reply = reply[:800] + "...\n\nFor more detailed information, please call us at +91 90192 31931."
            return jsonify({'reply': reply})
    except Exception as e:
        print(f"Gemini API error: {e}")
    
    # Fallback: Predefined responses for common jewelry queries
    keywords = {
        'price': 'Our jewelry prices vary by metal type and weight. Gold starts from ₹6,500, Silver from ₹240, and Diamond from ₹1,960. Visit our store or call +91 90192 31931 for current prices.',
        'gold': 'We offer beautiful gold jewelry including rings, chains, necklaces, and nose pins for women, men, and children. Gold pieces start from ₹6,500. Which item interests you?',
        'silver': 'Our silver collection includes elegant rings, chains, necklaces, and nose pins starting from ₹240. Perfect for both everyday wear and special occasions!',
        'diamond': 'We have premium diamond jewelry including rings, necklaces, and nose pins. Diamond pieces start from ₹1,960. Call us for custom designs!',
        'ring': 'We offer rings in gold, silver, and diamond for women, men, and children. Available in various designs and weights. What type interests you?',
        'chain': 'Our chains are available in gold, silver, and diamond. Gold chains start from ₹35,000, silver from ₹3,500. What style do you prefer?',
        'necklace': 'Beautiful necklaces in gold, silver, and diamond. Gold necklaces start from ₹42,000. We have designs for every occasion!',
        'delivery': 'We deliver across India in 3-7 business days. Free shipping on orders above ₹5,000. Call +91 90192 31931 for more details.',
        'return': 'We offer a 7-day return/exchange policy on all jewelry. Contact us at +91 90192 31931 to initiate returns.',
        'children': 'We have a special children\'s jewelry collection in gold and silver with safe, age-appropriate designs. Starting from ₹1,500.',
    }
    
    for keyword, response_text in keywords.items():
        if keyword in user_message:
            return jsonify({'reply': response_text})
    
    # Default fallback if no keywords match
    return jsonify({'reply': 'Thank you for your interest! We specialize in Gold, Silver, and Diamond jewelry for all occasions. What would you like to know? You can ask about prices, designs, delivery, or any of our products. Call us at +91 90192 31931 for personalized assistance.'})


if __name__ == '__main__':
    app.run(debug=True)  # reload trigger
