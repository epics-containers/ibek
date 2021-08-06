To recreate ioc.boot file after changes:

pipenv run ibek build-ioc ./tests/samples/yaml/pmac.ibek.yaml ./tests/samples/yaml/bl45p-mo-ioc-02.pmac.yaml /tmp/ioc
cp /tmp/ioc/bl45p-mo-ioc-02/config/ioc.boot ./tests/samples/helm/
