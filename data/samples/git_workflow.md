# Git 版本控制与协作流程

## Git 简介

Git 是一个开源的分布式版本控制系统，由 Linux 之父林纳斯·托瓦兹（Linus Torvalds）于 2005 年为管理 Linux 内核的开发而创建。与 SVN 等集中式版本控制系统不同，Git 的每个开发者本地都有一份完整的仓库副本，包含全部提交历史，因此提交、查看历史、创建分支等大部分操作都可以离线完成，而且速度很快。

Git 有三个重要的本地区域：

- 工作区（Working Directory）：电脑上能直接看到和编辑的文件；
- 暂存区（Staging Area，也叫 Index）：用 git add 把修改放进暂存区，准备下一次提交；
- 本地仓库（Repository）：用 git commit 把暂存区的内容保存为一次提交，记录在 .git 目录中。

此外还有远程仓库（Remote），例如托管在 GitHub、Gitee 或 GitLab 上的仓库，通过 git push 和 git pull 与本地仓库同步。

## 常用命令

| 命令 | 作用 |
| --- | --- |
| `git init` | 在当前目录新建一个 Git 仓库 |
| `git clone 仓库地址` | 把远程仓库克隆到本地 |
| `git status` | 查看工作区和暂存区的状态 |
| `git add 文件名` | 把修改加入暂存区 |
| `git commit -m "说明"` | 把暂存区的内容提交到本地仓库 |
| `git log --oneline` | 以简洁的形式查看提交历史 |
| `git diff` | 查看尚未暂存的修改 |
| `git branch` | 查看、创建或删除分支 |
| `git switch 分支名` | 切换分支（旧写法是 git checkout） |
| `git merge 分支名` | 把指定分支合并到当前分支 |
| `git rebase 分支名` | 把当前分支的提交移到指定分支的最新提交之后 |
| `git fetch` | 从远程仓库下载最新的提交，但不合并 |
| `git pull` | 拉取远程更新并合并到当前分支，相当于 fetch 加 merge |
| `git push` | 把本地提交推送到远程仓库 |
| `git stash` | 临时保存未提交的修改，让工作区恢复干净 |
| `git tag v1.0.0` | 给某个提交打上版本标签 |

## merge 与 rebase 的区别

git merge 和 git rebase 都可以把一个分支的修改整合到另一个分支，但方式不同：

- merge（合并）会保留两个分支完整的分叉历史，并生成一个新的“合并提交”。它不会改写已有的提交，操作安全，但分支多了以后历史图会比较杂乱；
- rebase（变基）会把当前分支上的提交逐个“搬”到目标分支的最新提交之后重新应用，得到一条干净的线性历史。但 rebase 会改写提交，提交的哈希值会发生变化。

使用 rebase 的黄金法则：不要对已经推送到公共远程仓库、并且别人可能基于它工作的分支执行 rebase，否则会给其他协作者带来麻烦。一般只在整理自己本地、尚未共享的提交时使用 rebase。

## reset 与 revert 的区别

撤销提交时常用 git reset 和 git revert：

- git reset 会把当前分支的指针移动到指定的提交，相当于“回到过去”。--soft 保留修改并留在暂存区，--mixed（默认）保留修改但撤出暂存区，--hard 会直接丢弃修改，需要谨慎使用；
- git revert 不会删除历史，而是新建一个提交来抵消指定提交的修改。对于已经推送到远程仓库的提交，应该使用 revert，而不是 reset。

## 分支管理策略

- Git Flow：使用 main（或 master）和 develop 两条长期分支，再配合 feature、release、hotfix 等短期分支，适合有明确版本发布周期的项目；
- GitHub Flow：只有一条长期的 main 分支。开发新功能时从 main 拉出功能分支，完成后发起 Pull Request，经过代码评审和自动化测试后合并回 main。流程简单，适合持续部署的项目；
- 主干开发（Trunk-Based Development）：所有开发者频繁地把小粒度的修改直接合并到主干，通常配合功能开关（Feature Flag）使用。

## 参与开源项目的 Pull Request 流程

1. Fork：在 GitHub 上把目标仓库复刻到自己的账号下；
2. Clone：把自己 Fork 出来的仓库克隆到本地；
3. 新建分支：例如执行 git switch -c fix-typo，不要直接在 main 分支上修改；
4. 修改并提交：按照项目的代码规范修改，编写清晰的提交信息；
5. Push：把分支推送到自己 Fork 的远程仓库；
6. 发起 Pull Request：在 GitHub 上向原仓库发起合并请求，说明修改的内容和原因；
7. 代码评审：根据维护者的评审意见继续修改，持续集成（CI）检查也需要全部通过；
8. 合并：维护者确认无误后，把 Pull Request 合并进主分支。

Gitee 上同样叫 Pull Request，GitLab 上则叫 Merge Request（合并请求），思路是一样的。

## 提交信息规范

很多开源项目遵循“约定式提交”（Conventional Commits）规范，提交信息的格式为“类型(范围): 描述”，例如“feat(retriever): 支持 BM25 检索”。常见的类型有：

- feat：新功能
- fix：修复缺陷
- docs：只修改了文档
- style：不影响代码含义的格式调整
- refactor：既不是新功能也不是修复缺陷的代码重构
- test：添加或修改测试
- chore：构建流程、依赖管理等杂项

规范的提交信息便于阅读历史，也可以用工具自动生成更新日志（CHANGELOG）。

## .gitignore 文件

.gitignore 文件用来声明不需要纳入版本控制的文件，例如虚拟环境目录 .venv/、Python 编译缓存 __pycache__/、IDE 配置目录 .idea/，以及保存 API Key 等敏感信息的 .env 文件。密钥一旦被提交并推送到公开仓库，即使之后删除，也仍然可以从提交历史中找回，因此必须立即作废并更换新的密钥。
