# CloudFormation ECS Tasks Function

This repository defines the Lamdba function `cfnEcsTasks`.

This function runs ECS tasks and polls the task until successful completion or failure.

## Build Instructions

Any dependencies need to defined in `src/requirements.txt`.  Note that you do not need to include `boto3`, as this is provided by AWS for Python Lambda functions.

To build the function and its dependencies:

`make build`

This will create the necessary dependencies in the `src` folder and create a ZIP package in the `target` folder.  This file is suitable for upload to the AWS Lambda service to create a Lambda function.

```
$ make build
=> Building cfnEcsTasks.zip...
Collecting cfn_resource (from -r requirements.txt (line 1))
Installing collected packages: cfn-resource
Successfully installed cfn-resource-0.2.2
updating: cfn_resource-0.2.2.dist-info/ (stored 0%)
updating: cfn_resource.py (deflated 67%)
updating: cfn_resource.pyc (deflated 62%)
updating: requirements.txt (stored 0%)
updating: setup.cfg (stored 0%)
updating: ecs_tasks.py (deflated 63%)
=> Built target/cfnEcsTasks.zip
```

### Function Naming

The default name for this function is `cfnEcsTasks` and the corresponding ZIP package that is generated is called `cfnEcsTasks.zip`.

If you want to change the function name, you can either update the `FUNCTION_NAME` setting in the `Makefile` or alternatively configure an environment variable of the same name to override the default function name.

## Publishing the Function

When you publish the function, you are simply copying the built ZIP package to an S3 bucket.  Before you can do this, you must ensure your enviornment is configured correctly with appropriate AWS credentials and/or profiles.

To specify the S3 bucket that the function should be published to, you can either configure the `S3_BUCKET` setting in the `Makefile` or alternatively configure an environment variable of the same name to override the default S3 bucket name.

> [Versioning](http://docs.aws.amazon.com/AmazonS3/latest/dev/Versioning.html) must be enabled on the S3 bucket

To deploy the built ZIP package:

`make publish`

This will upload the built ZIP package to the configured S3 bucket.

> When a new or updated package is published, the S3 object version will be displayed.

### Publish Example

```
$ make publish
...
...
=> Built target/cfnEcsTasks.zip
=> Publishing cfnEcsTasks.zip to s3://dev-dockerproductionaws-cfn-lambda...
=> Published to S3 URL: https://s3-ap-southeast-2.amazonaws.com/dev-dockerproductionaws-cfn-lambda/cfnEcsTasks.zip
=> S3 Object Version: pzMzf1hI7WawjGBz.3pPPa5APYlMmQ8F
```

## CloudFormation Usage

This function is designed to be called from a CloudFormation template as a custom resource.

The following custom resource calls this Lambda function when the resource is created, updated or deleted:

```
  MigrateTask:
    Type: "Custom::ECSTask"
    Properties:
      ServiceToken: "arn:aws:lambda:ap-southeast-2:012345678901:function:dev-cfnEcsTasks"
      Cluster: { "Ref": "ApplicationCluster" }
      TaskDefinition: { "Ref": "ApplicationTaskDefinition" }
      Count: 1              
      Timeout: 1800           # The maximum amount of time to wait for the task to complete - defaults to 290 seconds
      RunOnUpdate: True       # Controls if the task should run for update operations - defaults to True
      UpdateCriteria:         # Specifies criteria to determine if a task update should run
        - Container: app
          EnvironmentKeys:    # List of environment keys to compare.  The task is only run if the environment key value has changed.
            - DB_HOST
      PollInterval: 30        # How often to poll the status of a given task
      Overrides:              # Task definition overrides
        containerOverrides:
          - name: app
            command:
              - manage.py
              - migrate
            environment:
              - name SOME_VAR
                value
      Instances:              # Optional list of container instances to run the task on
        - arn:aws:ecs:ap-southeast-2:012345678901:container-instance/9d8698b5-5477-4b8b-bb63-dfd1e140b0d8

```

The following table describes the various properties:

| Property       | Description                                                                                                                                                                                                                                                                                                                                                                                          | Required | Default Value |
|----------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------|---------------|
| ServiceToken   | The ARN of the Lambda function                                                                                                                                                                                                                                                                                                                                                                       | Yes      |               |
| Cluster        | The name of the ECS Cluster to run the task on                                                                                                                                                                                                                                                                                                                                                       | Yes      |               |
| TaskDefinition | The family, family:revision or full ARN of the ECS task definition that the ECS task is executed from.                                                                                                                                                                                                                                                                                               | Yes      |               |
| Count          | The number of task instances to run.  If the Instances property is set, this count value is ignored as one task per instance will be run.  If set to 0, no tasks will be run (even if the Instances property is set).                                                                                                                                                                                | No       | 1             |
| Timeout        | The maximum time in seconds to wait for the task to complete successfully.                                                                                                                                                                                                                                                                                                                           | No       | 290           |
| RunOnUpdate    | Controls if the task should be run for update to the resource.                                                                                                                                                                                                                                                                                                                                       | No       | True          |
| UpdateCriteria | Optional list of criteria used to determine if the task should be run for an update to the resource.   If specified, you must configure the `Container` property as the name of a container in the task definition, and specify a list of environment variable keys using the `EnvironmentKey` property.  If any of the specified environment variable values  have changed, then the task will run. | No       |               |
| Overrides      | Optional task definition overrides to apply to the specified task definition.                                                                                                                                                                                                                                                                                                                        | No       |               |
| Instances      | Optional list of ECS container instances to run the task on.  If specified, you must use the ARN of each ECS container instance.                                                                                                                                                                                                                                                                     | No       |               |
| Triggers       | List of triggers that can be used to trigger updates to this resource, based upon changes to other resources.  This property is ignored by the Lambda function.  
