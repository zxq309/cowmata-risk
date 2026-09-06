from setuptools import setup, find_packages

setup(name='cowmata-activity-aux', version='1.0.0', packages=find_packages(),
      python_requires='>=3.8', install_requires=['numpy>=1.20'],
      package_data={'cowmata_activity_aux':['output.schema.json']},
      description='COWMATA per-cow activity features and auxiliary calving evidence')
