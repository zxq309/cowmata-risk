from setuptools import setup

setup(
    name="cowmata-temperature-aux",
    version="0.6.0",
    description="COWMATA temperature auxiliary decision module: B plus sustained cooling",
    packages=["cowmata_temperature_aux"],
    package_data={"cowmata_temperature_aux": ["model.json", "output.schema.json"]},
    python_requires=">=3.8",
    install_requires=["numpy>=1.20"],
)
