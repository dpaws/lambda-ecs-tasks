# Parameters
FUNCTION_NAME ?= cfnEcsTasks
S3_BUCKET ?= dev-dockerproductionaws-cfn-lambda
AWS_DEFAULT_REGION ?= ap-southeast-2

include Makefile.settings

build: clean
	@ ${INFO} "Building $(FUNCTION_NAME).zip..."
	@ rm -rf src/vendor
	@ cd src && pip install -t vendor/ -r requirements.txt --upgrade
	@ mkdir -p target
	@ cd src && zip -9 -r ../target/$(FUNCTION_NAME).zip * -x *.pyc
	@ ${INFO} "Built target/$(FUNCTION_NAME).zip"

publish: build
	@ ${INFO} "Publishing $(FUNCTION_NAME).zip to s3://$(S3_BUCKET)..."
	@ aws s3 cp --quiet target/$(FUNCTION_NAME).zip s3://$(S3_BUCKET)
	@ ${INFO} "Published to S3 URL: https://s3-$(AWS_DEFAULT_REGION).amazonaws.com/$(S3_BUCKET)/$(FUNCTION_NAME).zip"
	@ ${INFO} "S3 Object Version: $(S3_OBJECT_VERSION)"

clean:
	@ rm -rf src/*.pyc src/vendor target
	@ ${INFO} "Removed all distributions"