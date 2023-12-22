# Use an official Python runtime as a parent image
FROM python:3.10

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the dependencies file to the working directory
COPY Trading/requirements.txt ./

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your app's source code from your host to your image filesystem.
COPY . .

# Run your application's install and setup commands
RUN cd deps/ && \
    tar -xzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib/ && \
    ./configure --prefix=/usr && \
    make && \
    make install

# Ensure scripts in the container are executable
RUN chmod +x ./your_test_script.sh

# Define environment variable
ENV PYTHONPATH "${PYTHONPATH}:/usr/src/app"

# Run your application
ENTRYPOINT ["entrypoint.sh"]
