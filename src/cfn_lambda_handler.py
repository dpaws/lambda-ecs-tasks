import json
import logging
import urllib2
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

SUCCESS = 'SUCCESS'
FAILED = 'FAILED'

class CfnLambdaExecutionTimeoutError(Exception):
  def __init__(self,*args,**kwargs):
    Exception.__init__(self,*args,**kwargs)

def cfn_handler(func, base_response=None):

    def callback(url, data):
      request = urllib2.Request(
        url, 
        data=data,
        headers={'Content-Length': len(data),'Content-Type': ''}
      )
      request.get_method = lambda: 'PUT'

      try:
        urllib2.urlopen(request)
        logger.debug("Request to CloudFormation API succeeded")
      except urllib2.HTTPError as e:
        logger.error("Callback to CloudFormation API failed with status %d" % e.code)
        logger.error("Response: %s" % e.reason)
      except urllib2.URLError as e:
        logger.error("Failed to reach the CloudFormation API: %s" % e.reason)

    def decorator(event, context):
      response = {
        "StackId": event["StackId"],
        "RequestId": event["RequestId"],
        "LogicalResourceId": event["LogicalResourceId"],
        "Status": SUCCESS,
      }
      if event.get("PhysicalResourceId"):
        response["PhysicalResourceId"] = event["PhysicalResourceId"]
      if base_response:
        response.update(base_response)
      logger.debug("Received %s request with event: %s" % (event['RequestType'], json.dumps(event)))

      # Add event creation time 
      event['CreationTime'] = event.get('CreationTime') or int(time.time())
      timeout = event.get('Timeout')
      if timeout:
        finish = event['CreationTime'] + timeout
        if int(time.time()) > finish:
          logger.info("Function reached maximum timeout of %d seconds" % timeout)
          response.update({ 
            "Status": FAILED,
            "Reason": "The custom resource operation failed to complete within the user specified timeout of %d seconds" % timeout
          })
      else:
        try:
          response.update(func(event, context))
        except CfnLambdaExecutionTimeoutError as e:
          logger.info("Function approaching maximum Lambda execution timeout...")
          logger.info("Invoking new Lambda function...")
          try:
            boto3.client('lambda').invoke(
              FunctionName=context.function_name,
              InvocationType='Event',
              Payload=json.dumps(event))
            return
          except:
            logger.exception("Failed to invoke new Lambda function after maximum Lambda execution timeout")
            response.update({
              "Status": FAILED,
              "Reason": "Failed to invoke new Lambda function after maximum Lambda execution timeout"
            })            
        except:
          logger.exception("Failed to execute resource function")
          response.update({
            "Status": FAILED,
            "Reason": "Exception was raised while handling custom resource"
          })

      serialized = json.dumps(response)
      logger.info("Responding to '%s' request with: %s" % (event['RequestType'], serialized))
      callback(event['ResponseURL'], serialized)

    return decorator

class Handler:
  def __init__(self, decorator=cfn_handler):
    self._handlers = dict()
    self._decorator = decorator

  def __call__(self, event, context):
    request = event['RequestType']
    return self._handlers.get(request, self._empty())(event, context)

  def _empty(self):
    @self._decorator
    def empty(event, context):
      return {
        'Status': FAILED,
        'Reason': 'No handler defined for request type %s' % event['RequestType'],
      }
    return empty

  def create(self, func):
    self._handlers['Create'] = self._decorator(func)
    return func

  def update(self, func):
    self._handlers['Update'] = self._decorator(func)
    return func

  def delete(self, func):
    self._handlers['Delete'] = self._decorator(func)
    return func