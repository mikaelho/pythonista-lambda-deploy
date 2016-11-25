# pythonista-lambda-deploy

This is a Pythonista action script that will deploy the files in the current directory as an AWS Lambda function.

Script will:

- Create or update the AWS Lambda function
- Bu default, create or update an API endpoint, with permissions for accessing the Lambda function
- Optionally make the API endpoint return HTML content type (i.e. a web page) instead of JSON
- (To be implemented:) Optionally create a DynamoDB table and set the Lambda function with the rights to write to it

# Setup

To give the script access to AWS services, create file `awsconf.py` in the same directory as the `lambda-deploy.py` with the cresentials available from the AWS console:

    aws_id='YOUR_AWS_ID'
    aws_secret='YOUR_AWS_SECRET'
    aws_region='YOUR REGION, e.g. eu-west-1'

Then set up the `lambda-deploy.py` script in your Pythonista action ('screwdriver') menu.

# Creating an AWS Lambda function

... work in progress ...
