# Gitflow Workflow Guide for MiniAutoGen Contributors

## Introduction

This guide is intended for contributors to the MiniAutoGen project and provides an overview of how we use the Gitflow Workflow to organize project development.

## Overview of Gitflow

Gitflow is a branching strategy that involves multiple branches for different purposes, ensuring organization and smooth development.

### Main Branches

- **Main/Master**: This is the production code branch. It contains a version of the code that is in production.
- **Develop**: Branch for active development. All new features are merged here before being brought into the main branch.

### Support Branches

- **Feature Branches**: Created from the `develop` branch for new features.
- **Release Branches**: Created from `develop` to prepare for a release.
- **Hotfix Branches**: Created from `main/master` for urgent fixes.

## Gitflow Workflow Steps for MiniAutoGen

### 1. Developing New Features

1. **Create a Feature Branch**:
   ```bash
   git checkout develop
   git pull
   git checkout -b feature/[feature_name]
   ```
   *Replace `[feature_name]` with the name of your feature.*

2. **Develop Your Feature**:
   - Make your code changes.
   - Make regular commits to save your progress.

3. **Merge Back to Develop**:
   - After completing the feature, merge your branch into `develop`.
   - Submit a Pull Request (PR) to the `develop` branch for review.

### 2. Preparing a Release

1. **Create a Release Branch**:
   ```bash
   git checkout develop
   git checkout -b release/[version]
   ```
   *Replace `[version]` with the release version.*

2. **Finalize the Release**:
   - Complete all adjustments for the release.
   - Update the version number if necessary.
   - Open a PR to merge the release branch into both `main/master` and `develop`.

### 3. Hotfixes

1. **Create a Hotfix Branch**:
   ```bash
   git checkout main
   git checkout -b hotfix/[hotfix_name]
   ```
   *Replace `[hotfix_name]` with the name of the fix.*

2. **Implement the Hotfix**:
   - Make the necessary fixes.
   - Open a PR to merge the hotfix branch into both `main/master` and `develop`.

## Best Practices

- **PR Reviews**: All PRs should undergo reviews before merging.
- **Testing**: Test your changes extensively before requesting the merge.
- **Documentation**: Update the documentation as needed to reflect your changes.