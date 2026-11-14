import duckdb,sys
a,b=sys.argv[1],sys.argv[2]
con=duckdb.connect()
con.execute(f"ATTACH '{a}' AS A (READ_ONLY)"); con.execute(f"ATTACH '{b}' AS B (READ_ONLY)")
tabs=con.execute("SELECT schema_name, table_name FROM duckdb_tables() WHERE database_name='A' ORDER BY 1,2").fetchall()
views=con.execute("SELECT schema_name, view_name FROM duckdb_views() WHERE database_name='A' AND NOT internal ORDER BY 1,2").fetchall()
same=diff=0
for s,t in tabs+views:
    cols=[c for (c,) in con.execute(f"SELECT column_name FROM duckdb_columns() WHERE database_name='A' AND schema_name='{s}' AND table_name='{t}' ORDER BY column_index").fetchall()]
    keep=[c for c in cols if not c.startswith('_')] if s=='ods' else cols
    sel=', '.join(f'"{c}"' for c in keep)
    q=lambda db: con.execute(f"SELECT count(*), coalesce(sum(hash(x)),0) FROM (SELECT {sel} FROM {db}.{s}.{t}) x").fetchone()
    ra,rb=q('A'),q('B')
    if ra==rb: same+=1
    else: diff+=1; print('DIFF',s,t,ra,rb)
print('(ods: load-audit columns _* excluded)'); print(f'objects compared {len(tabs)} tables + {len(views)} views: identical {same}, different {diff}')
