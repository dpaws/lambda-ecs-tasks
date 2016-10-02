import time
import logging
import cfn_resource
from hashlib import md5
from ecs import EcsTaskManager, EcsTaskFailureError, EcsTaskExitCodeError
from validation import get_validator, validate
from voluptuous import MultipleInvalid, Invalid

# Set handler as the entry point for Lambda
handler = cfn_resource.Resource()

# Configure logging
log = logging.getLogger()
log.setLevel(logging.INFO)

# ECS Task Manager
task_mgr = EcsTaskManager()

def start_task(task):
  return task_mgr.start_task(
    cluster=task['Cluster'],
    task_definition=task['TaskDefinition'],
    overrides=task['Overrides'],
    count=task['Count'],
    instances=task['Instances'],
    started_by=task['StartedBy']
  )

def to_dict(items, key, value):
  return dict(zip([i[key] for i in items], [i[value] for i in items]))

def task_id(stack_id, resource_id):
  m = md5()
  m.update(stack_id + resource_id)
  return m.hexdigest()

def get_task_definition_values(task_definition_arn, update_criteria):
  task_definition = task_mgr.describe_task_definition(task_definition_arn)
  containers = to_dict(task_definition['containerDefinitions'],'name','environment')
  return [env['value'] for u in update_criteria for env in containers.get(u['Container'],{}) if env['name'] in u['EnvironmentKeys']]

def check_complete(task_result):
  if task_result.get('failures'):
    raise EcsTaskFailureError(task_result)
  tasks = task_result.get('tasks')
  return all(t.get('lastStatus') == 'STOPPED' for t in tasks)

def check_exit_codes(task_result):
  tasks = task_result['tasks']
  non_zero = [c.get('taskArn') for t in tasks for c in t.get('containers') if c.get('exitCode') != 0]
  if non_zero:
    raise EcsTaskExitCodeError(tasks, non_zero)

def poll(task):
  poll_interval = task['PollInterval'] or 10
  poll_count = task['Timeout'] / poll_interval + 1
  counter = 0
  task_result = task['TaskResult']
  log.info("Checking if task(s) have completed...")
  while counter < poll_count:
    complete = check_complete(task_result)
    if complete:
      check_exit_codes(task_result)
      return task_result
    else:
      log.info("Task(s) have not yet completed, checking again in %s seconds..." % poll_interval)
      time.sleep(poll_interval)
      tasks = task_result['tasks']
      task_arns = [t.get('taskArn') for t in tasks]
      task_result = task_mgr.describe_tasks(cluster=task['Cluster'], tasks=task_arns)
  raise TimeoutError("The tasks did not complete in the specified timeout of %s seconds", task['Timeout'])

def task_result_handler(func):
    def handle_task_result(*args, **kwargs):
      try:
        func(*args, **kwargs)
      except EcsTaskFailureError as e:
        return {"Status": "FAILED", "Reason": "A task failure occurred: %s" % e.failures}
      except EcsTaskExitCodeError as e:
        return {"Status": "FAILED", "Reason": "One or more containers failed with a non-zero exit code: %s" % e.non_zero}
      except (Invalid, MultipleInvalid) as e:
        return {"Status": "FAILED", "Reason": "One or more invalid properties: %s" % e}
      except TimeoutError as e:
        return {"Status": "FAILED", "Reason": "The task did not complete in the specified timeout of %s seconds" % task['Timeout']}
      except Exception as e:
        return {"Status": "FAILED", "Reason": "An exception occcured: %s" % e}
    return handle_task_result

# Event handlers
@handler.create
@task_result_handler
def handle_create(event, context):
  task = validate(event.get('ResourceProperties'))
  task['StartedBy'] = task_id(event.get('StackId'), event.get('LogicalResourceId'))
  if task['Count'] > 0:
    task['CreationTime'] = int(time.time())
    task['TaskResult'] = start(task)
    task['TaskResult'] = poll(task)
    log.info("Task completed with result: %s" % task['TaskResult'])
  return {"Status": "SUCCESS", "PhysicalResourceId": task['StartedBy']}

@handler.update
@task_result_handler
def handle_update(event, context):
  task = validate(event.get('ResourceProperties'))
  task['StartedBy'] = task_id(event.get('StackId'), event.get('LogicalResourceId'))
  update_criteria = task['UpdateCriteria']
  if task['RunOnUpdate'] and task['Count'] > 0:
    old_task = validate(event.get('OldResourceProperties'))
    if update_criteria:
      old_values = get_task_definition_values(old_task['TaskDefinition'],task['UpdateCriteria'])
      new_values = get_task_definition_values(task['TaskDefinition'],task['UpdateCriteria'])
      if old_values != new_values:
        task['CreationTime'] = int(time.time())
        task['TaskResult'] = start(task)
        task['TaskResult'] = poll(task)
        log.info("Task completed with result: %s" % task['TaskResult'])
  return {"Status": "SUCCESS", "PhysicalResourceId": task['StartedBy']}
  
@handler.delete
@task_result_handler
def handle_delete(event, context):
  task_id = task_id(event.get('StackId'), event.get('LogicalResourceId'))
  tasks = task_mgr.list_tasks(cluster=cluster, startedBy=task_id)
  for t in tasks:
    service_mgr.stop_task(cluster=cluster, task=t, reason='Delete requested for %s' % event.get('StackId'))