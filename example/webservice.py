# coding: utf-8

"""
This is a template Lambda service that returns
a web page (HTML). A HTML template is assumed to
be found in the same directory with the name
'main.html'.

You can run this file locally to test the results before deploying to AWS Lambda.
"""

import os

def handler(event = None, context = None):
  '''
  @awslambda @html
  '''
  with open('main.html') as file_in:
    main_html = file_in.read()
  return main_html % {
    'main_content': 'Hello ' + event['queryParams']['name']
  }

if __name__ == '__main__':
  import ui
  v = ui.WebView()
  html_content = handler({'queryParams': {'name': 'world'}})
  v.load_html(html_content)
  v.present()

