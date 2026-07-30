# Use an official Python runtime as a parent image
FROM python:3.10

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the rest of your app's source code from your host to your image filesystem.
COPY . .

# Run your application's install and setup commands
RUN cd deps/ && \
    tar -xzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib/ && \
    ./configure --prefix=/usr && \
    make && \
    make install && \
    cd ../..

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r Trading/requirements.txt

# Browser binary for Playwright-based scraping (Trading/stock/gurufocus) -
# the pip package alone doesn't ship the actual browser. Pin the install
# path instead of letting it default to ~/.cache/ms-playwright: GitHub
# Actions "container:" jobs override HOME to /github/home at runtime, which
# is different from HOME during this build, so the browser installed here
# would otherwise be looked for (and not found) in the wrong place.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN python3 -m playwright install --with-deps chromium

# Arguments that will be passed during the build
ARG GH_USERNAME
ARG CLONE_TOKEN

# Run git clone using the build arguments
RUN git clone https://${GH_USERNAME}:${CLONE_TOKEN}@github.com/doruirimescu/XTBApi.git
RUN cd XTBApi/ && \
    pip install . && \
    rm -rf XTBApi && \
    cd ..

# Define environment variable
ENV PYTHONPATH "${PYTHONPATH}:/usr/src/app"

# Run your application
ENTRYPOINT ["./script/entrypoint.sh"]
