# coding: utf-8

import os
import editor
import ast
import re
import json
import zipfile
import StringIO
import logging
import collections

import boto3

from awsconf import *
import botocore.exceptions

ConfStrings = collections.namedtuple('ConfStrings', 'awslambda noapi html')
conf_strings = ConfStrings('@awslambda', '@no-api', '@html')

current_dir = os.path.dirname(editor.get_path())

lambda_client = boto3.client('lambda', aws_access_key_id=aws_id, aws_secret_access_key=aws_secret, region_name=aws_region)

iam_client = boto3.client('iam', aws_access_key_id=aws_id, aws_secret_access_key=aws_secret, region_name=aws_region)

api_client = boto3.client('apigateway', aws_access_key_id=aws_id, aws_secret_access_key=aws_secret, region_name=aws_region)

def main():

  print '\n* Start AWS Lambda function deployment'
  conf = get_configuration()

  if not conf:
    logging.exception('Configuration not found, should have at least ' + conf_strings.awslambda + ' in the docstring of the handler function')
    return

  role_arn = set_up_role(conf['function_name'])
  if not role_arn:
    logging.exception('Could not get a role for the function')
    return
  conf['account_id'] = role_arn.split(':')[4]

  print '** Updating function code'

  func_arn = set_up_func(conf, role_arn)
  if not func_arn:
    logging.exception('Could not create or update the function')
    return

  if not 'no-api' in conf:
    print '** Setting up API endpoint'
    rest_api_id = set_up_api(conf, func_arn)

  if 'db' in conf:
    create_databases(conf['db'])

  print '** Deployment complete'

def get_configuration():
  '''
  Reads the docstring in the open file and finds AWS configuration information, starting with the magic string followed by JSON formatted key-value pairs. Remember that JSON uses double quotes for strings.
  '''
  lambda_function_name = os.path.basename(current_dir)
  current_file = os.path.basename(editor.get_path())
  if current_file.endswith('.py'):
    handler_first_part = current_file[:-3]
  file_text = editor.get_text()
  tree = ast.parse(file_text)

  conf = None
  for func in top_level_functions(tree.body):
    docstr = ast.get_docstring(func)
    if docstr:
      if conf_strings.awslambda in docstr:
        conf = {
                'function_name': lambda_function_name,
                'handler': handler_first_part + '.' + func.name
        }
        if conf_strings.noapi in docstr:
          conf['no-api'] = True
          print '** Will not update API endpoint'
        if conf_strings.html in docstr:
          conf['html'] = True
        return conf
  return None

def top_level_functions(body):
  return (f for f in body if isinstance(f, ast.FunctionDef))

def set_up_role(func_name):
  arn = None
  role_name = 'lambda-' + func_name + '-role'
  try:
    result = iam_client.get_role(RoleName = role_name)
    arn = result['Role']['Arn']
  except: pass
  if arn: return arn

  try:
    result = iam_client.create_role(
            Path = '/service-role/',
            RoleName = role_name,
            AssumeRolePolicyDocument = json.dumps(assume_role_policy_document)
    )
    arn = result['Role']['Arn']
  except: pass

  return arn

assume_role_policy_document = {
        'Version': '2012-10-17',
        'Statement': [{
                'Action': 'sts:AssumeRole',
                'Effect': 'Allow',
                'Principal': {'Service': 'lambda.amazonaws.com'}
        }]
}

def set_up_func(conf, role_arn):
  func_arn = None
  zip_contents = get_zipped()
  if get_lambda_conf(conf['function_name']):
    func_arn = update_lambda_func(conf, zip_contents)
  else:
    func_arn = create_lambda_func(conf, role_arn, zip_contents)
  return func_arn

def create_databases(db_conf):
  pass

def get_zipped():
  '''
  Returns the binary zipped contents of the directory the file openin the editor is in.
  '''
  in_mem_file = StringIO.StringIO()
  with zipfile.ZipFile(in_mem_file, 'w') as zip_file:
    zip_directory(current_dir, zip_file)
  return in_mem_file.getvalue()

def zip_directory(path, zip_file):
  count = 0
  for root, dirs, files in os.walk(path):
    for file in files:
      archive_name = os.path.join(root[len(path):], file)
      if archive_name.startswith('/'):
        archive_name = archive_name[1:]
      zip_file.write(os.path.join(root, file), archive_name)
      count += 1
  return count

def get_lambda_conf(func_name):
  '''
  Check whether the function already exists on Lambda. Returns configuration info if yes, or None if there is an error.
  '''
  result = None
  try:
    result = lambda_client.get_function_configuration(FunctionName = func_name)
  except botocore.exceptions.ClientError:
    pass
  return result

def create_lambda_func(conf, role_arn, code_zip):
  '''
  Creates a new Lambda function given the configuration and function code in a zip file. Returns the ARN of the created function.
  '''
  result = lambda_client.create_function(
          FunctionName = conf['function_name'],
          Runtime = 'python2.7',
          Role = role_arn,
          Handler = conf['handler'],
          Code = { 'ZipFile': code_zip }
  )
  return result['FunctionArn']

def update_lambda_func(conf, code_zip):
  result = lambda_client.update_function_code(
          FunctionName=conf['function_name'],
          ZipFile=code_zip
  )
  return result['FunctionArn']

def set_up_api(conf, func_arn):
  ''' Create/update api and deploy to 'prod' stage '''
  # Check for existing api
  api_id = None
  api_name = 'lambda-function-' + conf['function_name']
  try:
    apis = api_client.get_rest_apis()
    for api in apis['items']:
      if api['name'] == api_name:
        api_id = api['id']
  except: pass
  # Create API
  if not api_id:
    try:
      result = api_client.create_rest_api(name = api_name, description = 'API front-end created for a Lambda function by lambda_deploy.py')
      api_id = result['id']
    except: pass
  if not api_id:
    logging.exception('API not found and could not be created')
  # Update conf
  api_conf_template = api_conf_html if 'html' in conf else api_conf_json
  print '** API endpoint returns ' + 'HTML' if 'html' in conf else 'JSON'
  api_conf_template['info']['title'] = api_name

  api_conf_dump = json.dumps(api_conf_template)
  api_conf_dump = api_conf_dump.replace('@replace_lambda_function_url', 'arn:aws:apigateway:' + aws_region + ':lambda:path/2015-03-31/functions/' + func_arn + '/invocations')

  result = api_client.put_rest_api(restApiId = api_id, mode = 'overwrite', body = api_conf_dump)
  result = api_client.create_deployment(
    restApiId=api_id,
    stageName='prod'
  )
  invoke_permission_statement_id = 'apigateway-prod-lambda-' + conf['function_name']
  try:
    lambda_client.remove_permission(
      FunctionName=conf['function_name'],
      StatementId=invoke_permission_statement_id
    )
  except: pass
  lambda_client.add_permission(
    FunctionName=conf['function_name'],
    StatementId=invoke_permission_statement_id,
    Action='lambda:InvokeFunction',
    Principal='apigateway.amazonaws.com'
  )
  print 'Function available at https://%s.execute-api.%s.amazonaws.com/prod/' % (api_id, aws_region)

api_conf_html = {
  "swagger" : "2.0",
  "info" : {
    #"version" : "2016-10-31T16:16:50Z",
    "title" : "<replace>"
  },
  "basePath" : "/prod",
  "schemes" : [ "https" ],
  "paths" : {
    "/" : {
      "get" : {
        "consumes" : [ "application/json" ],
        "produces" : [ "text/html" ],
        "responses" : {
          "200" : {
            "description" : "200 response",
            "headers" : {
              "Content-Type" : {
                "type" : "string"
              }
            }
          }
        },
        "x-amazon-apigateway-integration" : {
          "uri" : "@replace_lambda_function_url",
          "passthroughBehavior" : "when_no_templates",
          "httpMethod" : "POST",
          "requestTemplates" : {
            "application/json" : "{\n  \"method\": \"$context.httpMethod\",\n  \"body\" : $input.json('$'),\n  \"headers\": {\n    #foreach($param in $input.params().header.keySet())\n    \"$param\": \"$util.escapeJavaScript($input.params().header.get($param))\" #if($foreach.hasNext),#end\n\n    #end\n  },\n  \"queryParams\": {\n    #foreach($param in $input.params().querystring.keySet())\n    \"$param\": \"$util.escapeJavaScript($input.params().querystring.get($param))\" #if($foreach.hasNext),#end\n\n    #end\n  },\n  \"pathParams\": {\n    #foreach($param in $input.params().path.keySet())\n    \"$param\": \"$util.escapeJavaScript($input.params().path.get($param))\" #if($foreach.hasNext),#end\n\n    #end\n  }  \n}"
          },
          "responses" : {
            "default" : {
              "statusCode" : "200",
              "responseParameters" : {
                "method.response.header.Content-Type" : "'text/html'"
              },
              "responseTemplates" : {
                "text/html" : "$input.path('$')"
              }
            }
          },
          "type" : "aws"
        }
      },
      "post" : {
        "consumes" : [ "application/json" ],
        "produces" : [ "text/html" ],
        "responses" : {
          "200" : {
            "description" : "200 response",
            "headers" : {
              "Content-Type" : {
                "type" : "string"
              }
            }
          }
        },
        "x-amazon-apigateway-integration" : {
          "uri" : "@replace_lambda_function_url",
          "passthroughBehavior" : "when_no_templates",
          "httpMethod" : "POST",
          "requestTemplates" : {
            "application/json" : "{\n  \"method\": \"$context.httpMethod\",\n  \"body\" : $input.json('$'),\n  \"headers\": {\n    #foreach($param in $input.params().header.keySet())\n    \"$param\": \"$util.escapeJavaScript($input.params().header.get($param))\" #if($foreach.hasNext),#end\n\n    #end\n  },\n  \"queryParams\": {\n    #foreach($param in $input.params().querystring.keySet())\n    \"$param\": \"$util.escapeJavaScript($input.params().querystring.get($param))\" #if($foreach.hasNext),#end\n\n    #end\n  },\n  \"pathParams\": {\n    #foreach($param in $input.params().path.keySet())\n    \"$param\": \"$util.escapeJavaScript($input.params().path.get($param))\" #if($foreach.hasNext),#end\n\n    #end\n  }  \n}"
          },
          "responses" : {
            "default" : {
              "statusCode" : "200",
              "responseParameters" : {
                "method.response.header.Content-Type" : "'text/html'"
              },
              "responseTemplates" : {
                "text/html" : "$input.path('$')"
              }
            }
          },
          "type" : "aws"
        }
      }
    }
  }
}

api_conf_json = {
  "swagger" : "2.0",
  "info" : {
    #"version" : "2016-11-01T05:02:15Z",
    "title" : "<replace>"
  },
  "basePath" : "/prod",
  "schemes" : [ "https" ],
  "paths" : {
    "/" : {
      "get" : {
        "consumes" : [ "application/json" ],
        "produces" : [ "application/json" ],
        "responses" : {
          "200" : {
            "description" : "200 response",
            "schema" : {
              "$ref" : "#/definitions/Empty"
            }
          }
        },
        "x-amazon-apigateway-integration" : {
          "uri" : "@replace_lambda_function_url",
          "passthroughBehavior" : "when_no_templates",
          "httpMethod" : "POST",
          "requestTemplates" : {
            "application/json" : "{\n  \"method\": \"$context.httpMethod\",\n  \"body\" : $input.json('$'),\n  \"headers\": {\n    #foreach($param in $input.params().header.keySet())\n    \"$param\": \"$util.escapeJavaScript($input.params().header.get($param))\" #if($foreach.hasNext),#end\n\n    #end\n  },\n  \"queryParams\": {\n    #foreach($param in $input.params().querystring.keySet())\n    \"$param\": \"$util.escapeJavaScript($input.params().querystring.get($param))\" #if($foreach.hasNext),#end\n\n    #end\n  },\n  \"pathParams\": {\n    #foreach($param in $input.params().path.keySet())\n    \"$param\": \"$util.escapeJavaScript($input.params().path.get($param))\" #if($foreach.hasNext),#end\n\n    #end\n  }  \n}"
          },
          "responses" : {
            "default" : {
              "statusCode" : "200"
            }
          },
          "type" : "aws"
        }
      },
      "post" : {
        "consumes" : [ "application/json" ],
        "produces" : [ "application/json" ],
        "responses" : {
          "200" : {
            "description" : "200 response",
            "schema" : {
              "$ref" : "#/definitions/Empty"
            }
          }
        },
        "x-amazon-apigateway-integration" : {
          "uri" : "@replace_lambda_function_url",
          "passthroughBehavior" : "when_no_templates",
          "httpMethod" : "POST",
          "requestTemplates" : {
            "application/json" : "{\n  \"method\": \"$context.httpMethod\",\n  \"body\" : $input.json('$'),\n  \"headers\": {\n    #foreach($param in $input.params().header.keySet())\n    \"$param\": \"$util.escapeJavaScript($input.params().header.get($param))\" #if($foreach.hasNext),#end\n\n    #end\n  },\n  \"queryParams\": {\n    #foreach($param in $input.params().querystring.keySet())\n    \"$param\": \"$util.escapeJavaScript($input.params().querystring.get($param))\" #if($foreach.hasNext),#end\n\n    #end\n  },\n  \"pathParams\": {\n    #foreach($param in $input.params().path.keySet())\n    \"$param\": \"$util.escapeJavaScript($input.params().path.get($param))\" #if($foreach.hasNext),#end\n\n    #end\n  }  \n}"
          },
          "responses" : {
            "default" : {
              "statusCode" : "200"
            }
          },
          "type" : "aws"
        }
      }
    }
  },
  "definitions" : {
    "Empty" : {
      "type" : "object",
      "title" : "Empty Schema"
    }
  }
}

plain_api_conf = {
  "swagger" : "2.0",
  "info" : {
    "version" : "2016-11-01T04:22:35Z",
    "title" : "StoreAPI"
  },
  "basePath" : "/prod",
  "schemes" : [ "https" ],
  "paths" : {
    "/" : {
      "get" : {
        "produces" : [ "application/json" ],
        "responses" : {
          "200" : {
            "description" : "200 response",
            "schema" : {
              "$ref" : "#/definitions/Empty"
            }
          }
        },
        "x-amazon-apigateway-integration" : {
          "uri" : "arn:aws:apigateway:eu-west-1:lambda:path/2015-03-31/functions/arn:aws:lambda:eu-west-1:004070725733:function:syncstore/invocations",
          "passthroughBehavior" : "when_no_match",
          "httpMethod" : "POST",
          "responses" : {
            "default" : {
              "statusCode" : "200"
            }
          },
          "type" : "aws"
        }
      }
    }
  },
  "definitions" : {
    "Empty" : {
      "type" : "object",
      "title" : "Empty Schema"
    }
  }
}

'''
mapping_template = {
  "method": "$context.httpMethod",
  "body" : $input.json('$'),
  "headers": {
    #foreach($param in $input.params().header.keySet())
    "$param": "$util.escapeJavaScript($input.params().header.get($param))" #if($foreach.hasNext),#end

    #end
  },
  "queryParams": {
    #foreach($param in $input.params().querystring.keySet())
    "$param": "$util.escapeJavaScript($input.params().querystring.get($param))" #if($foreach.hasNext),#end

    #end
  },
  "pathParams": {
    #foreach($param in $input.params().path.keySet())
    "$param": "$util.escapeJavaScript($input.params().path.get($param))" #if($foreach.hasNext),#end

    #end
  }
}
'''

if __name__ == '__main__':
  main()

