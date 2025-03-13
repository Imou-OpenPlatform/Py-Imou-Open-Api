##  打包
python setup.py sdist bdist_wheel

## 上传
twine upload dist/*      