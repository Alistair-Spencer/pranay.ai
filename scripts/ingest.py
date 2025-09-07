# scripts/ingest.py
import sys, os, glob
sys.path.append(os.path.dirname(os.path.dirname(__file__)))  # allow 'from retriever import Retriever'

from retriever import Retriever

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("folder", help="folder containing .pdf/.txt/.md")
    args = p.parse_args()

    folder = os.path.abspath(args.folder)
    if not os.path.isdir(folder):
        print(f"Folder not found: {folder}"); return

    paths = []
    for root, _, _ in os.walk(folder):
        paths.extend(glob.glob(os.path.join(root, "*.pdf")))
        paths.extend(glob.glob(os.path.join(root, "*.txt")))
        paths.extend(glob.glob(os.path.join(root, "*.md")))
        paths.extend(glob.glob(os.path.join(root, "*.markdown")))

    if not paths:
        print(f"No ingestible files found in {folder}"); return

    r = Retriever(persist_dir=os.getenv("CHROMA_DIR", "chroma_db"))
    before = r.collection.count()
    r.ingest(paths)
    after = r.collection.count()
    print(f"✅ Ingest complete. Files: {len(paths)} | Chunks now: {after} (added {after - before}).")

if __name__ == "__main__":
    main()
