#!/usr/bin/env python3
"""
Setup script for FTC Predictor Local Data Sync

This script helps set up the local environment for running data sync operations.
"""

import os
import sys
import subprocess
import json
from pathlib import Path

def setup_aws_credentials():
    """Check and guide AWS credentials setup"""
    print("=== AWS Credentials Check ===")
    
    # Check if AWS CLI is installed
    try:
        result = subprocess.run(['aws', '--version'], 
                              capture_output=True, text=True, check=True)
        print(f"✅ AWS CLI found: {result.stdout.strip()}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ AWS CLI not found. Please install it:")
        print("   https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html")
        return False
    
    # Check AWS credentials
    try:
        result = subprocess.run(['aws', 'sts', 'get-caller-identity'], 
                              capture_output=True, text=True, check=True)
        identity = json.loads(result.stdout)
        print(f"✅ AWS credentials configured for: {identity.get('Arn', 'Unknown')}")
        return True
    except subprocess.CalledProcessError:
        print("❌ AWS credentials not configured. Run:")
        print("   aws configure")
        print("   Then enter your AWS access key, secret key, and region (us-east-1)")
        return False

def install_dependencies():
    """Install Python dependencies"""
    print("\n=== Installing Dependencies ===")
    
    requirements_file = Path(__file__).parent / "local_sync_requirements.txt"
    
    if not requirements_file.exists():
        print("❌ Requirements file not found")
        return False
    
    try:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', str(requirements_file)], 
                      check=True)
        print("✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False

def check_aws_services():
    """Test connection to AWS services"""
    print("\n=== Testing AWS Connection ===")
    
    try:
        # Add the aws directory to path
        aws_dir = Path(__file__).parent / "aws"
        sys.path.insert(0, str(aws_dir))
        
        # Test DynamoDB connection
        from services.dynamodb_service import DynamoDBService
        
        print("✅ DynamoDB service import successful")
        
        # Test FTC API service
        from services.ftc_api_service import FTCApiService
        
        print("✅ FTC API service import successful")
        
        # Test AWS Secrets Manager access
        import boto3
        secrets_client = boto3.client('secretsmanager')
        try:
            # Try to access the credentials (don't actually retrieve them in setup)
            response = secrets_client.describe_secret(SecretId='arn:aws:secretsmanager:us-east-1:843578292678:secret:FTC-API-Credentials-stage-0KqPsx')
            print("✅ AWS Secrets Manager access successful")
        except Exception as e:
            print(f"⚠️  Warning: Cannot access FTC API credentials: {e}")
            print("   Make sure you have permission to access ftc-api-credentials-stage")
            return False
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Service test failed: {e}")
        return False

def main():
    """Main setup function"""
    print("FTC Predictor Local Data Sync Setup")
    print("=" * 40)
    
    success = True
    
    # Check AWS credentials
    if not setup_aws_credentials():
        success = False
    
    # Install dependencies
    if not install_dependencies():
        success = False
    
    # Test AWS services
    if not check_aws_services():
        success = False
    
    print("\n" + "=" * 40)
    
    if success:
        print("✅ Setup completed successfully!")
        print("\nYou can now run the local data sync:")
        print("   python local_data_sync.py --season 2024 --sync all")
        print("   python local_data_sync.py --season 2024 --sync teams")
        print("   python local_data_sync.py --season 2024 --sync events")
        print("   python local_data_sync.py --season 2024 --sync matches")
    else:
        print("❌ Setup incomplete. Please resolve the issues above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
