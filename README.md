# Serverless-Function-Execution-Platform
Docker-based python/javascript function execution with an API server

Expected to be run in a linux environment where docker, docker-compose, streamlit needs to be installed

chmod +x setup-environment.sh start-all.sh
./setup-environment.sh 
./start-all.sh

To stop:
docker-compose -f docker-compose.frontend.yml down (Add -v if you desire to clear the database)
docker ps -q --filter "ancestor=python-function" | xargs -r docker stop
docker ps -q --filter "ancestor=python-function" | xargs -r docker rm
