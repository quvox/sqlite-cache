# Sqlite3 based DB Cache Module

DBアクセスを高速化するために、Sqlite3を用いて簡易的なキャッシュを実現するためのモジュール。

Pythonでの利用を想定しているが、動作速度を向上するために、主要処理はGoで記述する。

AWS Lambdaのようなサーバレス環境での並列実行を想定しており、キャッシュ効率はそれほど高くないかもしれないが、なるべく軽く単純な処理で、staleはさせず、キャッシュがないよりはそれなりにマシになるということを目標にする。



## 想定するDBテーブルスキーマの特徴

* 複数のテナントがテーブルを共有しており、プライマリキーにテナントIDが含まれる（複合キーの一部でも良い）
* テナントごとに、1レコードでも更新があれば、そのテナントのキャッシュを無効化しても良い（それほどに更新頻度はかなり少ない）



## 使い方

### コマンドライン

使い方は、ヘルプに記載されている。
```bash
sqcache help
```

初期化、登録、検索は、すべて**JSON形式**でsqcacheの標準入力に与える。
```bash
echo 'INIT {"base_dir": "./cache", "max_size": 100, "cap": 0.8}' | sqcache
echo {"table": "users", "tenant_id": "tenant1", "freshness": 1234567890, "bind": "key1", "content": "data" | sqcache
echo {"table": "users", "tenant_id": "tenant1", "freshness": 1234567890, "bind": "key1"} | sqcache
```



#### ライブラリ

#### Pythonで利用する

sqcachelib.[バージョン].soをctypesで呼び出すサンプルコードは、example/python_ctypes_client.pyに示す。



### go mod

Goのモジュール化は未対応


