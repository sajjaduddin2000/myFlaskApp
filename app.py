import os
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions, ContentSettings
from azure.storage.fileshare import ShareServiceClient, ContentSettings as FileContentSettings
from flask import Flask, request, redirect
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

app = Flask(__name__)

# Fetch connection string and account details from environment
connect_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")  # Ensure this is set
account_key = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")    # Ensure this is set
container_name = "photos"
file_share_name = os.getenv("AZURE_FILE_SHARE_NAME")    # Ensure this is set

# Validate connection string
if not connect_str or not account_name or not account_key or not file_share_name:
    raise ValueError("AZURE_STORAGE_CONNECTION_STRING, AZURE_STORAGE_ACCOUNT_NAME, AZURE_STORAGE_ACCOUNT_KEY, or AZURE_FILE_SHARE_NAME is missing in .env!")

# Initialize Blob Service Client
blob_service_client = BlobServiceClient.from_connection_string(connect_str)

# Initialize File Share Service Client
file_share_service_client = ShareServiceClient.from_connection_string(connect_str)
file_share_client = file_share_service_client.get_share_client(file_share_name)

# Ensure container exists (with public access for demo)
try:
    container_client = blob_service_client.get_container_client(container_name)
    container_client.get_container_properties()  # Check if container exists
except Exception as e:
    print(f"Error: {e}. Creating container...")
    container_client = blob_service_client.create_container(container_name)

# Ensure file share exists
try:
    file_share_client.get_share_properties()
except Exception as e:
    print(f"Error: {e}. Creating file share...")
    file_share_client.create_share()

@app.route("/")
def view_photos():
    blobs = container_client.list_blobs()
    files = file_share_client.list_directories_and_files()
    img_html = "<div style='display: flex; flex-wrap: wrap; gap: 1em;'>"

    for blob in blobs:
        try:
            # Generate SAS token for secure access with 1-day expiry
            sas_token = generate_blob_sas(
                account_name=account_name,
                container_name=container_name,
                blob_name=blob.name,
                account_key=account_key,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.utcnow() + timedelta(days=1)
            )

            # Construct URL with SAS token
            blob_url = f"https://{account_name}.blob.core.windows.net/{container_name}/{blob.name}?{sas_token}"
            img_html += f'<div><img src="{blob_url}" width="270" height="180" style="border-radius: 10px; border: 1px solid #ddd; margin: 5px;"></div>'
        except Exception as e:
            print(f"Error generating SAS token for {blob.name}: {e}")

    for file in files:
        if not file.is_directory:
            try:
                # Generate SAS token for secure access with 1-day expiry
                sas_token = generate_blob_sas(
                    account_name=account_name,
                    share_name=file_share_name,
                    file_path=file.name,
                    account_key=account_key,
                    permission=BlobSasPermissions(read=True),
                    expiry=datetime.utcnow() + timedelta(days=1)
                )

                # Construct URL with SAS token
                file_url = f"https://{account_name}.file.core.windows.net/{file_share_name}/{file.name}?{sas_token}"
                img_html += f'<div><img src="{file_url}" width="270" height="180" style="border-radius: 10px; border: 1px solid #ddd; margin: 5px;"></div>'
            except Exception as e:
                print(f"Error generating SAS token for {file.name}: {e}")

    img_html += "</div>"
    return f"""
    <head>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body>
        <nav class="navbar navbar-dark bg-primary mb-4">
            <div class="container">
                <a class="navbar-brand" href="/">Photos App</a>
            </div>
        </nav>
        <div class="container">
            <h3>Upload new File</h3>
            <form method="post" action="/upload-photos" enctype="multipart/form-data">
                <input type="file" name="photos" multiple accept=".png,.jpg,.jpeg">
                <button type="submit" class="btn btn-primary mt-2">Submit</button>
            </form>
            <hr>
            <h3>Uploaded Images</h3>
            {img_html}
        </div>
    </body>
    """

@app.route("/upload-photos", methods=["POST"])
def upload_photos():
    if "photos" not in request.files:
        return redirect("/")
    
    for file in request.files.getlist("photos"):
        if file.filename == "":
            continue
        try:
            # Upload to Blob Storage
            blob_client = container_client.get_blob_client(file.filename)
            blob_client.upload_blob(
                file.read(),
                overwrite=True,
                content_settings=ContentSettings(content_type=file.content_type)
            )

            # Upload to File Share
            file_client = file_share_client.get_file_client(file.filename)
            file.seek(0)  # Reset file pointer to the beginning
            file_client.upload_file(
                file,
                content_settings=FileContentSettings(content_type=file.content_type)
            )
        except Exception as e:
            print(f"Upload failed: {str(e)}")
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)