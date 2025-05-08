from flask import Flask, render_template, request, redirect, url_for, flash
from git import Repo, GitCommandError
import os

app = Flask(__name__)
app.secret_key = "supersecret"  # For flash messages

# Directory where repos will be cloned
CLONE_BASE_DIR = os.path.join(os.getcwd(), "cloned_repos")
os.makedirs(CLONE_BASE_DIR, exist_ok=True)

REPO_PATHS = {}  # Mapping for repo name to path

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        repo_url = request.form.get("repo_url", "").strip()
        local_path = request.form.get("local_path", "").strip()

        if not repo_url and not local_path:
            flash("Please provide either a GitLab repository URL or a local repository path.")
            return redirect(url_for("index"))

        repo_name = ""
        repo_path = ""

        try:
            if repo_url:
                repo_name = repo_url.rstrip(".git").split("/")[-1]
                repo_path = os.path.join(CLONE_BASE_DIR, repo_name)

                if not os.path.exists(repo_path):
                    Repo.clone_from(repo_url, repo_path)
                    flash(f"Cloned {repo_name} successfully!")
                else:
                    flash(f"Repository '{repo_name}' is already cloned.")

            elif local_path:
                if not os.path.isdir(local_path) or not os.path.exists(os.path.join(local_path, ".git")):
                    flash("The provided path is not a valid Git repository.")
                    return redirect(url_for("index"))

                repo_path = local_path
                repo_name = os.path.basename(local_path)

            REPO_PATHS[repo_name] = repo_path
            return redirect(url_for("repo_status", repo=repo_name))

        except GitCommandError as e:
            flash(f"Git error: {str(e)}")
            return redirect(url_for("index"))

    return render_template("index.html")

@app.route("/repo/<repo>")
def repo_status(repo):
    repo_path = REPO_PATHS.get(repo, os.path.join(CLONE_BASE_DIR, repo))

    try:
        repo_obj = Repo(repo_path)
        status_output = repo_obj.git.status("--short").splitlines()
        files = [{"status": line[:2].strip(), "file": line[3:].strip()} for line in status_output]
        commit_history = list(repo_obj.iter_commits(repo_obj.active_branch.name, max_count=5))

        return render_template("repo_status.html", repo=repo, files=files, commit_history=commit_history, 
                               current_branch=repo_obj.active_branch.name, branches=[head.name for head in repo_obj.heads])

    except Exception as e:
        flash(f"Could not open repo: {str(e)}")
        return redirect(url_for("index"))

@app.route("/repo/<repo>/commit", methods=["POST"])
def commit_files(repo):
    repo_path = REPO_PATHS.get(repo, os.path.join(CLONE_BASE_DIR, repo))

    try:
        repo_obj = Repo(repo_path)
    except Exception as e:
        flash(f"Could not open repo: {str(e)}")
        return redirect(url_for("index"))

    selected_files = request.form.getlist("files")
    commit_msg = request.form.get("message", "").strip()
    branch_name = request.form.get("branch")

    if not selected_files:
        flash("No files selected for commit.")
        return redirect(url_for("repo_status", repo=repo))
    if not commit_msg:
        flash("Commit message is required.")
        return redirect(url_for("repo_status", repo=repo))

    # Switch to the selected branch
    try:
        if branch_name != repo_obj.active_branch.name:
            repo_obj.git.checkout(branch_name)

        for file in selected_files:
            repo_obj.git.add(file)

        repo_obj.index.commit(commit_msg)

        try:
            origin = repo_obj.remote(name="origin")
            origin.push()
            flash("Changes committed and pushed successfully.")
        except Exception:
            flash("Committed locally, but push failed or no remote set.")

    except GitCommandError as e:
        flash(f"Git error: {str(e)}")

    return redirect(url_for("repo_status", repo=repo))

@app.route("/repo/<repo>/branches", methods=["GET", "POST"])
def manage_branches(repo):
    repo_path = REPO_PATHS.get(repo, os.path.join(CLONE_BASE_DIR, repo))

    try:
        repo_obj = Repo(repo_path)
    except Exception as e:
        flash(f"Failed to access repo: {str(e)}")
        return redirect(url_for("index"))

    if request.method == "POST":
        action = request.form.get("action")
        branch_name = request.form.get("branch_name").strip()

        try:
            if action == "create":
                repo_obj.git.checkout("-b", branch_name)
                flash(f"Created and switched to new branch '{branch_name}'")
            elif action == "switch":
                repo_obj.git.checkout(branch_name)
                flash(f"Switched to branch '{branch_name}'")
        except GitCommandError as e:
            flash(f"Git error: {str(e)}")

        return redirect(url_for("manage_branches", repo=repo))

    current_branch = repo_obj.active_branch.name
    branches = [head.name for head in repo_obj.heads]

    return render_template("branches.html", repo=repo, branches=branches, current_branch=current_branch)

if __name__ == "__main__":
    app.run(debug=True)
