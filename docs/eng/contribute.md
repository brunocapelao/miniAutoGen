Aqui está o documento "How to Contribute to MiniAutoGen" atualizado para incorporar a prática do Gitflow:

---

# How to Contribute to MiniAutoGen

Thank you for your interest in contributing to MiniAutoGen! This guide is aligned with the Gitflow workflow to ensure a smooth contribution process.

## Step 1: Fork and Clone the Repository

To start, you need your own copy of the repository.

1. **Fork the Repository**:
   - Visit the MiniAutoGen GitHub repository: [MiniAutoGen Repo](https://github.com/brunocapelao/miniAutoGen).
   - Click on 'Fork' at the top right corner to create a copy in your GitHub account.

2. **Clone the Repository**:
   - Open your terminal.
   - Clone the forked repository:
     ```
     git clone https://github.com/your-username/miniAutoGen.git
     ```
   - Replace `your-username` with your GitHub username.

## Step 2: Set Up Your Local Environment

1. **Navigate to the Project Directory**:
   - Enter the cloned directory:
     ```
     cd miniautogen
     ```

2. **Install Dependencies**:
   - Ensure you have Poetry installed ([Poetry's official site](https://python-poetry.org/)).
   - Install dependencies:
     ```
     poetry install
     ```

## Step 3: Align with Gitflow Workflow

**Read the [Gitflow Workflow Pattern](gitflow.md)**

1. **Sync with `develop` Branch**:
   - Sync your local `develop` branch with the upstream repository:
     ```
     git checkout develop
     git pull origin develop
     ```

2. **Create a Feature or Hotfix Branch**:
   - For new features:
     ```
     git checkout -b feature/your-feature-name develop
     ```
   - For hotfixes:
     ```
     git checkout -b hotfix/your-hotfix-name main
     ```
   - Use descriptive names for your branches.

## Step 4: Make Your Changes

1. **Edit or Add Files**:
   - Implement your changes, ensuring they align with project standards.

2. **Commit Changes**:
   - Stage your changes:
     ```
     git add .
     ```
   - Commit with a descriptive message:
     ```
     git commit -m "A brief description of the changes"
     ```

## Step 5: Push Changes and Create a Pull Request

1. **Push Your Changes**:
   - Push to your fork:
     ```
     git push origin your-branch-name
     ```

2. **Submit a Pull Request**:
   - On your forked GitHub repository, click 'Pull Request' > 'New Pull Request'.
   - Select your branch and describe your changes.
   - Create the PR against the `develop` branch for features, or `main` for hotfixes.

## Step 6: Await Review

- PRs are reviewed by maintainers.
- Address feedback if any.
- Approved PRs will be merged according to Gitflow procedures.

## Additional Tips

- **Stay Up to Date**: Regularly sync your fork and branches.
- **Adhere to Guidelines**: Follow the project's coding standards and contribution guidelines.

Thank you for contributing to MiniAutoGen. We value your contributions and commitment to making this project great!