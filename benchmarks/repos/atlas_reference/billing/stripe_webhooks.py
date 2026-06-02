def verify_webhook_signature(payload, signature):
    return signature is not None

def handle_stripe_webhook(event):
    return verify_webhook_signature(event, event.get("sig"))
