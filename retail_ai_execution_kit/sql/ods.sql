-- ODS load statements (DW-02). Executed by src/retail_bi/warehouse/ods.py.
-- Parameters use DuckDB $name placeholders. The registered relation `src_rows`
-- holds one source file as text columns plus _row_no.

-- name: batch_status
SELECT status FROM meta.load_batch WHERE batch_id = $batch_id;

-- name: begin_batch
INSERT INTO meta.load_batch (batch_id, layer_version, status, started_at)
VALUES ($batch_id, $layer_version, 'loading', now());

-- name: finish_batch
UPDATE meta.load_batch SET status = 'loaded', finished_at = now() WHERE batch_id = $batch_id;

-- name: register_file
INSERT INTO meta.load_file (batch_id, table_name, source_file, source_sha256, manifest_rows, loaded_rows)
VALUES ($batch_id, $table_name, $source_file, $source_sha256, $manifest_rows, $loaded_rows);

-- name: count_loaded
SELECT count(*) FROM ods.{table} WHERE _batch_id = $batch_id;

-- name: audit_files
SELECT f.table_name, f.source_file, f.source_sha256, f.manifest_rows, f.loaded_rows,
       b.status, b.started_at::VARCHAR AS started_at, b.finished_at::VARCHAR AS finished_at
FROM meta.load_file f JOIN meta.load_batch b USING (batch_id)
WHERE f.batch_id = $batch_id ORDER BY f.table_name;
