import uuid

def generate_guid():
    return str(uuid.uuid4())

# Generate a new GUID
new_guid = generate_guid()
print(f"Generated GUID: {new_guid}")