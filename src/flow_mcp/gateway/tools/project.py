"""Project management MCP tools."""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from flow_mcp.browser.session import get_browser
from flow_mcp.config import get_settings
from flow_mcp.db.project_dao import ProjectDAO
from flow_mcp.pages.home_page import HomePage


def register_project_tools(mcp: FastMCP, project_dao: ProjectDAO) -> None:
    """Register project-related MCP tools."""

    @mcp.tool(name="website_open", description="Open Google Flow website in browser")
    async def website_open(url: str = "") -> dict[str, Any]:
        """Navigate browser to Flow website or specific URL."""
        target = url or get_settings().google_flow_base_url
        browser = get_browser()
        tab = browser.latest_tab
        assert not isinstance(tab, str)
        tab.get(target)
        home = HomePage(tab)
        home.dismiss_modals()
        return {"status": "success", "message": f"Opened {target}", "current_url": tab.url}

    @mcp.tool(name="project_list", description="List all Google Flow projects")
    async def project_list() -> dict[str, Any]:
        """List all projects discovered on Flow and in local database."""
        browser = get_browser()
        tab = browser.latest_tab
        assert not isinstance(tab, str)
        home = HomePage(tab)
        home.open()
        projects = home.get_projects()

        # Sync into project_dao
        for name, p in projects.items():
            await project_dao.upsert_project(name, "master_local_worker", p["local_uuid"])

        return {
            "status": "success",
            "count": len(projects),
            "projects": list(projects.values()),
        }

    @mcp.tool(name="project_open", description="Open a specific Google Flow project by name")
    async def project_open(project_name: str = "default") -> dict[str, Any]:
        """Open a project in the browser, creating it if it does not exist."""
        browser = get_browser()
        tab = browser.latest_tab
        assert not isinstance(tab, str)
        home = HomePage(tab)
        home.open()

        projects = home.get_projects()
        base_url = get_settings().google_flow_base_url

        if project_name in projects:
            local_uuid = projects[project_name]["local_uuid"]
            url = f"{base_url}/project/{local_uuid}"
            tab.get(url)
            await project_dao.upsert_project(project_name, "master_local_worker", local_uuid)
            return {"status": "success", "project_name": project_name, "url": url}

        # Create new project
        new_uuid = home.create_project()
        home.open()
        home.rename_project(new_title=project_name, project_uuid=new_uuid)
        url = f"{base_url}/project/{new_uuid}"
        tab.get(url)
        await project_dao.upsert_project(project_name, "master_local_worker", new_uuid)
        return {"status": "success", "project_name": project_name, "url": url, "created": True}

    @mcp.tool(name="project_create", description="Create a new Google Flow project")
    async def project_create(project_name: str) -> dict[str, Any]:
        """Explicitly create and name a new Flow project."""
        return await project_open(project_name)

    @mcp.tool(name="project_rename", description="Rename a Google Flow project")
    async def project_rename(old_name: str, new_name: str) -> dict[str, Any]:
        """Rename an existing project."""
        browser = get_browser()
        tab = browser.latest_tab
        assert not isinstance(tab, str)
        home = HomePage(tab)
        home.open()
        success = home.rename_project(new_title=new_name, old_title=old_name)
        if success:
            local_uuid = await project_dao.get_local_uuid(old_name, "master_local_worker")
            if local_uuid:
                await project_dao.delete_project(old_name, "master_local_worker")
                await project_dao.upsert_project(new_name, "master_local_worker", local_uuid)
            return {"status": "success", "old_name": old_name, "new_name": new_name}
        return {"status": "error", "message": f"Failed to rename project from '{old_name}' to '{new_name}'"}
