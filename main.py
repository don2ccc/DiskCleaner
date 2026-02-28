import sys
from pathlib import Path

from core.scanner import scan_directories
from core.rules import evaluate_candidates, RuleOptions
from core.ai_analyzer import AiAnalyzer, AiAnalysisOptions
from core.cleaner import delete_directory, DeleteOptions


def main() -> None:
    # 默认扫描 C:\ 根目录
    root = Path("C:/")

    # 排除系统目录，只做统计不作为清理候选
    excluded_roots = {
        Path("C:/Windows"),
        Path("C:/Program Files"),
        Path("C:/Program Files (x86)"),
        Path("C:/ProgramData"),
    }

    print(f"扫描目录: {root}")
    stats = list(scan_directories(root=root, excluded_roots=excluded_roots))

    # 规则评估：时间 + 体积
    rule_options = RuleOptions(
        high_priority_size_bytes=1 * 1024 * 1024 * 1024,  # 1GB
        high_priority_days=180,
        normal_priority_size_bytes=500 * 1024 * 1024,      # 500MB
        normal_priority_days=90,
    )
    candidates = list(evaluate_candidates(stats, rule_options))

    # 只展示 Top 20 最大的候选目录
    candidates.sort(key=lambda c: c.directory.size_bytes, reverse=True)
    top = candidates[:20]

    # 是否启用 AI 分析
    ai = AiAnalyzer()
    use_ai = input("是否启用 AI 分析帮助判断目录用途？(y/N): ").strip().lower() == "y"
    ai_options = AiAnalysisOptions(enable_ai=use_ai)
    if use_ai:
        base_url = input("请输入 AI 服务 base_url（例如 https://your-host/api），留空则仅使用本地启发式: ").strip()
        if base_url:
            ai_options.api_base_url = base_url
        api_key = input("如果需要 API Key，请输入（可留空）: ").strip()
        if api_key:
            ai_options.api_key = api_key

    print("\n建议关注的目录 (按体积排序，Top 20):")
    for idx, cand in enumerate(top, start=1):
        dir_path = cand.directory.path
        size_gb = cand.directory.size_bytes / (1024 ** 3)
        print(f"[{idx}] {dir_path} - 大小: {size_gb:.2f} GB - 优先级: {cand.priority.name}")

        if ai_options.enable_ai:
            analysis = ai.analyze_path(cand.directory, ai_options)
            print(f"    AI 判断: {analysis.summary} (置信度 {analysis.confidence:.0%})")

    # 是否执行删除操作
    do_delete = input("\n是否要对上述目录执行删除操作？(y/N): ").strip().lower() == "y"
    if not do_delete:
        print("未执行任何删除操作。")
        return

    index_str = input("请输入要处理的编号列表，用逗号分隔，例如 1,3,5；直接回车取消: ").strip()
    if not index_str:
        print("未选择任何目录，取消删除。")
        return

    try:
        indices = {int(x) for x in index_str.split(",") if x.strip()}
    except ValueError:
        print("编号格式有误，取消删除。")
        return

    direct = input("是否直接删除（不经过回收站）？(y/N): ").strip().lower() == "y"
    options = DeleteOptions(use_trash=not direct)

    print("\n即将处理以下目录：")
    to_delete_paths = []
    for idx, cand in enumerate(top, start=1):
        if idx in indices:
            print(f"- [{idx}] {cand.directory.path}")
            to_delete_paths.append(cand.directory.path)

    if not to_delete_paths:
        print("未匹配到任何编号，取消删除。")
        return

    confirm = input("确认执行删除操作吗？(y/N): ").strip().lower()
    if confirm != "y":
        print("已取消删除。")
        return

    for path in to_delete_paths:
        try:
            delete_directory(path, options)
        except Exception as exc:  # pragma: no cover - 运行期错误仅提示
            print(f"删除 {path} 失败: {exc}")

    if options.use_trash:
        print("已将选中目录移入回收站。")
    else:
        print("已直接删除选中目录，请谨慎核对。")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已取消扫描。")
        sys.exit(1)
