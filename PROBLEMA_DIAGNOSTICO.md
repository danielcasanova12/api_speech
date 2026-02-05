sudo docker-compose down --volumes
sudo docker system prune -af
sudo docker-compose up --build -d
sudo docker-compose logs