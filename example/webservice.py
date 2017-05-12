# coding: utf-8

"""
This is a template Lambda service that returns
a web page (HTML). A HTML template is assumed to
be found in the same directory with the name
'main.html'.

You can run this file locally to test the results before deploying to AWS Lambda.

After deployment, you can add '?name=world' to the end of the service url to see the page change.
"""

import os

def handler(event = None, context = None):
  """
  This is the Lambda function that handles the request to AWS.
  
  Name of this functionnis not significant. 
  Deployer recognizes this as the right
  function because this comment has the magic
  string @awslambda.
  
  API endpoint created in front of the Lambda
  function will be expected to return a web page
  because of the @html string in this comment.
  """
  
  name = 'nameless'
  
  try:
    name = event['queryParams']['name']
  except KeyError:
    pass
  
  with open('main.html') as file_in:
    main_html = file_in.read()
  return main_html % {
    'main_content': 'Hello ' + name
  }

if __name__ == '__main__':
  """
  This part of the file is for local testing only.
  HTML returned by the handler function is
  displayed in a WebView component.
  """
  import ui
  v = ui.WebView()
  html_content = handler({'queryParams': {'name': 'world'}})
  v.load_html(html_content)
  v.present()

