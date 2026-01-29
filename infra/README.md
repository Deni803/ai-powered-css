# Infra

This folder holds runtime infrastructure assets for local and EC2 deployments.

## Files
- `docker-compose.yml`: Postgres-only local stack (Frappe + RAG + Qdrant).
- `env.example`: template for `infra/.env`.
- `nginx.conf`: production Nginx reverse proxy for `bookyourshow.duckdns.org` (TLS + WebSocket + routing).

## Nginx (EC2)
Current deployment path:
```
/etc/nginx/sites-available/ai-css.conf
```
The contents of that file should match `infra/nginx.conf`.

## TLS (Let's Encrypt)
We use Certbot + Nginx plugin:
```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d bookyourshow.duckdns.org --preferred-challenges http
```

## Notes
- `/socket.io/` is proxied to the Frappe realtime service (port 9000).
- `/` goes to the main Frappe site (port 8000).
- `/dashboard/` and `/vector-api/` are Qdrant showcase routes.
- `/rag/` is an optional RAG service showcase route.
