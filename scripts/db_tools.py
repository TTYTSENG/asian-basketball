"""Read-only SQLite queries, UTF-8 CSV exports and snapshot backups."""
import argparse,csv,sqlite3,sys
from pathlib import Path
from contextlib import closing

DEFAULT=Path(__file__).resolve().parents[1]/'data/basketball.sqlite3'

def read_connection(path):
    path=Path(path).resolve()
    if not path.is_file():raise FileNotFoundError(f'找不到資料庫：{path}')
    conn=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=5)
    conn.execute('PRAGMA foreign_keys=ON');conn.execute('PRAGMA query_only=ON')
    return conn

def run(args):
    with closing(read_connection(args.db)) as conn:
        if args.command=='status':
            print('資料庫：',Path(args.db).resolve())
            print('SQLite：',sqlite3.sqlite_version,'；結構版本：',conn.execute('PRAGMA user_version').fetchone()[0])
            print('完整性：',conn.execute('PRAGMA integrity_check').fetchone()[0])
            print('外鍵問題：',len(conn.execute('PRAGMA foreign_key_check').fetchall()))
            for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
                safe=name.replace('"','""');print(name,conn.execute(f'SELECT COUNT(*) FROM "{safe}"').fetchone()[0])
        elif args.command=='backup':
            output=Path(args.output).resolve();output.parent.mkdir(parents=True,exist_ok=True)
            # Exclusive creation avoids silently replacing an existing backup or source DB.
            with output.open('xb'):pass
            with closing(sqlite3.connect(output)) as dest:
                conn.backup(dest)
                if dest.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('備份完整性檢查失敗')
            print('已備份：',output)
        else:
            sql=args.sql or Path(args.file).read_text(encoding='utf-8-sig')
            cursor=conn.execute(sql)
            if cursor.description is None:raise ValueError('僅支援回傳資料的查詢')
            headers=[c[0] for c in cursor.description]
            if args.csv:
                output=Path(args.csv).resolve();output.parent.mkdir(parents=True,exist_ok=True)
                with output.open('x',encoding='utf-8-sig',newline='') as out:
                    writer=csv.writer(out);writer.writerow(headers)
                    count=0
                    for row in cursor:writer.writerow(['NULL' if x is None else x for x in row]);count+=1
                print(f'已匯出 {count} 筆：{output}（NULL 代表缺值）')
            else:
                print('\t'.join(headers))
                for row in cursor:print('\t'.join('NULL' if x is None else str(x) for x in row))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',type=Path,default=DEFAULT,help='預設為網站 data/basketball.sqlite3')
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('status',help='唯讀完整性與筆數檢查')
    backup=sub.add_parser('backup',help='建立不覆蓋既有檔案的備份');backup.add_argument('output')
    query=sub.add_parser('query',help='執行一個唯讀 SQL 查詢')
    source=query.add_mutually_exclusive_group(required=True);source.add_argument('--sql');source.add_argument('--file')
    query.add_argument('--csv',help='CSV 匯出路徑，不覆蓋既有檔案')
    try:run(parser.parse_args())
    except (OSError,sqlite3.Error,ValueError) as exc:print('操作失敗：',exc,file=sys.stderr);return 1
    return 0

if __name__=='__main__':raise SystemExit(main())
