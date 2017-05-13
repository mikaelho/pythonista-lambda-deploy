# pythonista-lambda-deploy

This is a Pythonista action script that will deploy the files in the current directory as an [AWS Lambda](https://aws.amazon.com/lambda/) function.

Script will:

- Create or update the AWS Lambda function
- By default, create or update an API endpoint, with permissions for accessing the Lambda function
- Optionally make the API endpoint return HTML content type (i.e. a web page) instead of JSON

To be implemented:

- Optionally create an S3 public or private bucket, and set the Lambda function with access rights
- Optionally create a DynamoDB table and set the Lambda function with the rights to write to it

# Installation

Create a suitable directory. In stash, move to that directory and get the files with:

git clone https://github.com/mikaelho/pythonista-lambda-deploy.git

# Setup

To give the script access to AWS services, create file `awsconf.py` in the same directory as the `lambda-deploy.py` with the credentials available from the AWS console:

    aws_id='YOUR_AWS_ID'
    aws_secret='YOUR_AWS_SECRET'
    aws_region='YOUR REGION, e.g. eu-west-1'

Then include the `lambda-deploy.py` script in your Pythonista action menu ('screwdriver' in the upper right corner, 'Edit', then 'plus' to add the script with your choice of icon and color).

# First deployment

Move to the `example` directory and open up `webservice.py`. Deploy it by running the deployer from the action menu. Script reports a url that you can click to see the function running on AWS.

# Re-deploying and other considerations

AWS Lambda functions are deployed by zipping the whole directory that you handler in. If you need some additional packages, you need to install them in the same directory so that they get carried along to AWS. You do not need to include Boto, the AWS Python client package.

If you need resources like images, a convenient option is to put them on S3 and turn on the bucket option that makes the bucket available as a web site.

AWS Lambda function name is the name of the directory where your handler function is. You can develop and keep re-deploying your function, and the deployer will update the AWS Lambda function. But if you change the directory name, the deployer will create a new AWS Lambda function and an API endpoint with a different URL.

# License

Do what you want with it, but do not blame me if something goes wrong.

