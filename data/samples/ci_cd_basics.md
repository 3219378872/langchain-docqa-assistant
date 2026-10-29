# 持续集成与自动化构建

## 什么是持续集成

持续集成（Continuous Integration，CI）是一种软件开发实践：团队成员频繁地（通常每天多次）把代码合并到共享的主干分支，每次合并都会自动触发构建和测试，从而尽早发现集成错误。持续集成的核心原则包括：维护单一的代码仓库、让构建自动化、让构建能够自我测试、每个人每天都向主干提交代码、保持构建快速，以及构建失败时优先修复。

在持续集成的基础上，还有两个经常被提到的概念：

- 持续交付（Continuous Delivery）：代码通过自动化测试后，始终处于可以随时发布的状态，但部署到生产环境仍需要人工确认；
- 持续部署（Continuous Deployment）：通过全部自动化测试的修改会被自动部署到生产环境，无需人工干预。

两者的英文缩写都是 CD，区别在于最后发布到生产环境这一步是否自动完成。

## 常见的 CI/CD 工具

- GitHub Actions：GitHub 内置的自动化平台，用仓库中的 YAML 文件定义工作流，公开仓库可以免费使用；
- GitLab CI/CD：GitLab 内置的流水线工具，配置文件是仓库根目录下的 .gitlab-ci.yml；
- Jenkins：老牌的开源自动化服务器，插件生态丰富，通常需要自行部署和维护；
- 其他：CircleCI、Travis CI、Gitee Go 等。

## GitHub Actions 的核心概念

- 工作流（Workflow）：一个自动化流程，用 YAML 文件定义，存放在仓库的 .github/workflows/ 目录下；
- 事件（Event）：触发工作流的条件，由 on 字段指定，例如 push（推送代码）、pull_request（发起合并请求）、schedule（定时触发）和 workflow_dispatch（手动触发）；
- 作业（Job）：工作流由一个或多个作业组成，不同作业默认并行执行，也可以用 needs 声明依赖关系；
- 步骤（Step）：作业中按顺序执行的单个任务，可以是一条 shell 命令（run），也可以是一个现成的 Action（uses）；
- 运行器（Runner）：执行作业的机器，用 runs-on 指定，例如 ubuntu-latest；
- 矩阵（Matrix）：用 strategy.matrix 让同一个作业在多个 Python 版本或多个操作系统上分别运行。

下面是一个 Python 项目的示例工作流，它会在每次推送代码和发起 Pull Request 时，分别在两个 Python 版本上安装依赖并运行测试：

```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-python@v7
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -r requirements.txt
      - run: pytest
```

## 构建工具与依赖管理

不同的编程语言有各自的构建和依赖管理工具：

| 语言 | 常用工具 | 依赖描述文件 |
| --- | --- | --- |
| Python | pip、uv、Poetry | requirements.txt、pyproject.toml |
| Java | Maven、Gradle | pom.xml、build.gradle |
| JavaScript | npm、pnpm、Yarn | package.json |
| C/C++ | Make、CMake | Makefile、CMakeLists.txt |
| Go | go 命令 | go.mod |
| Rust | Cargo | Cargo.toml |

为了让构建结果可以复现，应该锁定依赖的版本范围，并使用虚拟环境（例如 Python 的 venv）或容器来隔离项目依赖，避免出现“在我电脑上能运行”的问题。Python 项目通常把依赖写在 requirements.txt 中，再通过 pip install -r requirements.txt 一键安装。

## 语义化版本

语义化版本（Semantic Versioning，SemVer）规定版本号的格式为“主版本号.次版本号.修订号”（MAJOR.MINOR.PATCH）：

- 主版本号：做了不兼容的 API 修改时递增；
- 次版本号：以向下兼容的方式新增功能时递增；
- 修订号：做了向下兼容的问题修正时递增。

例如从 1.4.2 升级到 1.5.0 表示新增了功能并且保持兼容，而升级到 2.0.0 则意味着可能存在不兼容的改动。依赖声明中的“>=1.0,<2”就是利用了语义化版本：允许自动升级到兼容的新版本，同时避开可能不兼容的下一个主版本。

## 容器化

Docker 可以把应用及其运行环境（操作系统库、语言运行时、依赖包）打包成镜像，保证应用在开发、测试和生产环境中的行为一致。镜像的构建步骤写在 Dockerfile 中，常用指令有 FROM（指定基础镜像）、WORKDIR（设置工作目录）、COPY（复制文件）、RUN（构建时执行命令）、EXPOSE（声明端口）和 CMD（容器启动时执行的命令）。在 CI 流水线中，通常会在测试通过后自动构建镜像并推送到镜像仓库。
