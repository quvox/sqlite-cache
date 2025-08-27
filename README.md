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

初期化、登録、検索は、すべて**シンプルなテキストコマンド**でsqcacheの標準入力に与える。
```bash
echo 'INIT ./cache 100 0.8' | sqcache
echo 'SET users tenant1 fresh1 key1 data' | sqcache
echo 'GET users tenant1 fresh1 key1' | sqcache
echo 'DELETE users' | sqcache
echo 'CLOSE' | sqcache
```

**利用可能なコマンド:**
- `INIT base_dir max_size cap` - キャッシュシステムの初期化
  - `base_dir`: キャッシュファイルの保存ディレクトリ
  - `max_size`: 最大キャッシュサイズ（MB、整数値）
  - `cap`: LRU削除の閾値（0.0-1.0の小数値）
- `SET table tenant_id freshness bind content` - キャッシュデータの登録
  - `table`: テーブル名
  - `tenant_id`: テナントID
  - `freshness`: フレッシュネス文字列
  - `bind`: バインドキー
  - `content`: 保存するデータ
- `GET table tenant_id freshness bind` - キャッシュデータの取得
- `DELETE table` - テーブル内の全キャッシュデータの削除
- `CLOSE` - キャッシュシステムの終了

**レスポンス形式:**
- `OK: <result>` - 成功
- `ERROR: <reason>` - 失敗
- `MISS: <reason>` - キャッシュミス



#### ライブラリ

#### Pythonで利用する

sqcachelib.[バージョン].soをctypesで呼び出すサンプルコードは、examples/python_ctypes_client.pyに示す。

**利用可能なサンプル:**
- `examples/python_ctypes_client.py` - フル機能のPythonクライアント（クラスベース）
- `examples/python_simple_ctypes.py` - シンプルなPythonクライアント（関数ベース）
- `examples/test_cache_lru.py` - LRUアルゴリズムのテストケース
- `examples/bash_client.sh` - Bashクライアントの実装例

### ビルドとテスト

**ビルド:**
```bash
make build          # コマンドラインツールのビルド
make build-lib       # 共有ライブラリのビルド
make build-all       # 全てのビルド
```

**テスト:**
```bash
make test           # 全てのサンプルコードの実行テスト
```

**クロスプラットフォームビルド（Linux用）:**
```bash
make build-linux-musl          # Zig CC使用のLinux x86_64用ビルド
make build-lib-linux-musl      # Zig CC使用のLinux x86_64用ライブラリビルド
make build-lib-linux-arm64-musl # Zig CC使用のLinux ARM64用ライブラリビルド
make build-lib-linux-all       # 両方のLinuxアーキテクチャを一度にビルド
```

**AWS Lambda用ビルド（Amazon Linux 2）:**
```bash
make build-lib-lambda          # Amazon Linux 2 Docker内でx86_64用ライブラリビルド
make build-lib-lambda-arm64    # Amazon Linux 2 Docker内でARM64用ライブラリビルド
make build-lib-lambda-all      # 両方のLambdaアーキテクチャを一度にビルド
```

### go mod

Goのモジュール化は未対応


