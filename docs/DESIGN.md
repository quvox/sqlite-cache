# 設計

## キャッシュシステム構成

キャッシュ情報はSqlite3に保管する。基本的にはkey-valueストアとして利用する。

キャッシュファイル（sqlite3のDBファイル）は、テーブルごと、テナントIDごと、フレッシュネスごとに作成する。

```text
base_dir/
  ├── table1/
  │   ├── tenant_001/
  │   │   └── [timestamp].db
  │   ├── tenant_002/
  │   │   └── [timestamp].db
  │   └── tenant_003/
  │       └── [timestamp].db
  ├── table2/
  │   ├── tenant_001/
  │   │   └── [timestamp].db
  │   └── tenant_002/
  │       └── [timestamp].db
  └── users/
      ├── tenant_001/
      │   └── [timestamp].db
      └── tenant_002/
          └── [timestamp].db
```

table1, table2, usersはテーブル名である。
tenant_001, tenant_002は各テーブルのプライマリキーの値（テナントを表す値）である。
[timestamp]は、テーブルの該当プライマリキーのいずれかのレコードに書き込みが発生した時に、その時の時刻のUNIXTIMEをフレッシュネス値とし、それをキャッシュファイルのファイル名にする。



### SQLiteのテーブルスキーマ

キャッシュファイルはsqlite3のDBファイルであり、以下のスキーマを持つ。

```sql
CREATE TABLE cache
(
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    bind          TEXT NOT NULL,
    content       BLOB NOT NULL,
    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

また、bindとlast_accessedにインデックスを貼る。
```sql
CREATE INDEX idx_bind ON cache (bind);
CREATE INDEX idx_last_accessed ON cache (last_accessed);
```



## キャッシュファイルのライフサイクル

* キャッシュ検索には、テーブル名、テナントID、フレッシュネス値と、バインド値を与える
  - キャッシュヒットすれば、キャッシュレコードの最新アクセス時刻だけを更新し、キャッシュコンテンツを返す(UPDATE...RETURNINGを使う)
* キャッシュファイルが存在しない場合は、テナントIDのディレクトリ以下のすべてのファイルを削除する（古いキャッシュファイルを削除する）
* キャッシュの更新は、テーブル名、テナントID、フレッシュネス値と、バインド値とキャッシュコンテンツを与える
* キャッシュファイル自体を作成する場合は、テーブル名、テナントIDのディレクトリを作成してから、 キャッシュファイルを作成する
* キャッシュファイルには、最大サイズと、最大サイズを超えそうな時に自動的に古いレコードを削除するロジックを組み込む（LRUアルゴリズムで削除する）



## 実装方針

* キャッシュ制御部分はGoで実装し、以下のバイナリをbuild/の下に出力する
  - コマンドラインアプリケーション(sqcache)
  - キャッシュ制御機能のAPIを外部に提供するsharedライブラリ(sqcachelib)
  - sharedライブラリは、さらにmacおよびlinux用にクロスビルドして、build/mac/およびbuild/linux/に出力する
  - make allでは、コマンドラインアプリ、ライブラリ（mac/linux用）をすべてビルドする
* キャッシュ制御機能は、ワンバイナリで動作するようにし、ビルドしてreleaseする
  - ダイナミックリンクライブラリに依存させない
* Pythonからctypesを使ってキャッシュ制御機能を呼び出すためのサンプルを実装する
* 各dbファイルには、生成時に以下のpragmaを設定する
  - `PRAGMA journal_mode = OFF;`（WALモードでの書き込み）
  - `PRAGMA synchronous = NORMAL;`（書き込みの同期を通常に設定）



## キャッシュ制御機能のAPI

| 関数名 | 引数（JSON形式ではなく、個別に与える）            | 説明                                                         |
| ------ |--------------------------------------------| ------------------------------------------------------------ |
| Init   | base_dir, max_size, cap                    | キャッシュへのアクセス準備。max_sizeはMB単位、capは割合（0〜0.95）。max_sizeを超えそうになったら、前レコード数のうちcapの割合までレコードを削除する |
| Get    | table, tenant_id, freshness, bind          | キャッシュデータを探す                                       |
| Set    | table, tenant_id, freshness, bind, content | キャッシュデータを登録する。キャッシュファイルがなければ、ライフサイクルで説明した処理を実施し、キャッシュファイルを作ってから登録する。 |
| Delete | table                                      | 指定テーブルのフォルダを削除する（ただ削除するだけ）         |


#### 引数の形

| 引数名      | 型       | 説明                       |
| ----------- |---------|--------------------------|
| base_dir    | string  | キャッシュファイルのベースディレクトリ      
| max_size    | int     | キャッシュファイルの最大サイズ(MB)      |
| cap         | float64 | キャッシュファイルの最大サイズを超えそう     
| table       | string  | テーブル名                    |
| tenant_id   | string  | テナントID                   |
| freshness   | string  | フレッシュネス値                 |
| bind        | string  | バインド値                    |
| content     | []byte  | キャッシュコンテンツ(sqliteではBLOB) |



## テストコード

テストコード(example/text_cache_lru.py)は、以下のシナリオをPythonで実装する。なお、ctypesを使ってキャッシュ制御機能を呼び出すこと。

* max_size=10MB、cap=0.5で初期化
* 1レコードが100kB程度のサイズのコンテンツを作成する（コンテンツの最初にbind値を入れておく）
* freshness="fresh1"かつbind値として1〜200までの整数を与える
* freshness="fresh1"かつ1〜90までの整数のbind値のレコードを登録する
* freshness="fresh1"かつ1〜90までの適当なbind値30個を使って、キャッシュを検索する。すべてキャッシュヒットすること
* freshness="fresh1"かつ91〜200までの整数のbind値のレコードを登録する
* freshness="fresh1"かつ1〜99までの適当なbind値30個を使って、キャッシュを検索する。すべてキャッシュミスすること
* freshness="fresh1"かつ131〜200までの適当なbind値30個を使って、キャッシュを検索する。すべてキャッシュヒットすること
* freshness="fresh2"かつbind値が1のレコードを検索しようとする
* 検索に失敗し、その後freshness="fresh1"のキャッシュファイルが削除されていることを確認する
* freshness="fresh2"かつbind値が1〜10のレコードを登録する
* freshness="fresh2"かつ1〜10までのbind値使って、キャッシュを検索する。すべてキャッシュヒットすること
