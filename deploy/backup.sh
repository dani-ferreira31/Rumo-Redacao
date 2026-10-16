#!/bin/sh
# Backup diário: dump do Postgres + arquivos do storage, com rotação.
# Roda dentro do container "backup" (imagem postgres:16).
set -eu

KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
HOUR="${BACKUP_HOUR:-3}"

run_backup() {
  stamp=$(date +%Y%m%d-%H%M)
  echo "[backup] iniciando ${stamp}"
  pg_dump --format=custom --file="/backups/db-${stamp}.dump.tmp" \
    && mv "/backups/db-${stamp}.dump.tmp" "/backups/db-${stamp}.dump"
  tar -czf "/backups/storage-${stamp}.tar.gz.tmp" -C /data storage \
    && mv "/backups/storage-${stamp}.tar.gz.tmp" "/backups/storage-${stamp}.tar.gz"
  find /backups -type f \( -name 'db-*.dump' -o -name 'storage-*.tar.gz' \) -mtime "+${KEEP_DAYS}" -delete
  echo "[backup] concluído ${stamp}"
}

if [ "${1:-}" = "now" ]; then
  run_backup
  exit 0
fi

while true; do
  # dorme até a próxima ocorrência de HOUR:00 (no fuso TZ do container)
  now=$(date +%s)
  target=$(date -d "$(date +%Y-%m-%d) ${HOUR}:00" +%s)
  [ "$target" -le "$now" ] && target=$((target + 86400))
  sleep $((target - now))
  run_backup || echo "[backup] FALHOU"
done
