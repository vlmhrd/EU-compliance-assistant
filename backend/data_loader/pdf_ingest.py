import os
import sys
from pathlib import Path
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_environment_variables():
    load_dotenv()
    
    required_vars = ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'S3_BUCKET_NAME']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        sys.exit(1)
    
    return {
        'aws_access_key_id': os.getenv('AWS_ACCESS_KEY_ID'),
        'aws_secret_access_key': os.getenv('AWS_SECRET_ACCESS_KEY'),
        'bucket_name': os.getenv('S3_BUCKET_NAME'),
        'aws_region': os.getenv('AWS_REGION', 'us-east-1'),  
        'pdf_folder': os.getenv('PDF_FOLDER_PATH', './pdfs'),  
        's3_prefix': os.getenv('S3_PREFIX', 'documents/')  
    }

def create_s3_client(aws_access_key_id, aws_secret_access_key, aws_region):
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=aws_region
        )
        # Test the connection
        s3_client.list_buckets()
        logger.info("Successfully connected to AWS S3")
        return s3_client
    except NoCredentialsError:
        logger.error("AWS credentials not found or invalid")
        sys.exit(1)
    except ClientError as e:
        logger.error(f"Error connecting to S3: {e}")
        sys.exit(1)

def get_pdf_files(folder_path):
    """Get list of all PDF files in the specified folder"""
    folder = Path(folder_path)
    
    if not folder.exists():
        logger.error(f"Folder does not exist: {folder_path}")
        sys.exit(1)
    
    pdf_files = list(folder.glob("*.pdf"))
    pdf_files.extend(list(folder.glob("*.PDF")))  # Include uppercase extension
    
    if not pdf_files:
        logger.warning(f"No PDF files found in {folder_path}")
        return []
    
    logger.info(f"Found {len(pdf_files)} PDF files")
    return pdf_files

def upload_file_to_s3(s3_client, file_path, bucket_name, s3_key):
    """Upload a single file to S3"""
    try:
        file_size = file_path.stat().st_size
        logger.info(f"Uploading {file_path.name} ({file_size} bytes) to s3://{bucket_name}/{s3_key}")
        
        s3_client.upload_file(
            str(file_path),
            bucket_name,
            s3_key,
            ExtraArgs={
                'ContentType': 'application/pdf',
                'Metadata': {
                    'original_filename': file_path.name,
                    'upload_timestamp': str(int(Path(file_path).stat().st_mtime))
                }
            }
        )
        logger.info(f"Successfully uploaded {file_path.name}")
        return True
        
    except ClientError as e:
        logger.error(f"Failed to upload {file_path.name}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error uploading {file_path.name}: {e}")
        return False

def main():
    """Main function to orchestrate the PDF upload process"""
    logger.info("Starting PDF to S3 upload process")
    
    # Load environment variables
    config = load_environment_variables()
    
    # Create S3 client
    s3_client = create_s3_client(
        config['aws_access_key_id'],
        config['aws_secret_access_key'],
        config['aws_region']
    )
    
    # Get PDF files
    pdf_files = get_pdf_files(config['pdf_folder'])
    
    if not pdf_files:
        logger.info("No files to upload")
        return
    
    # Upload files
    successful_uploads = 0
    failed_uploads = 0
    
    for pdf_file in pdf_files:
        # Create S3 key (path in bucket)
        s3_key = f"{config['s3_prefix']}{pdf_file.name}"
        
        if upload_file_to_s3(s3_client, pdf_file, config['bucket_name'], s3_key):
            successful_uploads += 1
        else:
            failed_uploads += 1
    
    # Summary
    logger.info(f"Upload complete: {successful_uploads} successful, {failed_uploads} failed")
    
    if failed_uploads > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()