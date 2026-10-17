from importlib.metadata import entry_points


class Registry:
    def __init__(self, group="scene_stages"):
        self.group = group

    def available(self) -> list[str]:
        return sorted(ep.name for ep in entry_points(group=self.group))

    def resolve(self, name: str):
        matches = [ep for ep in entry_points(group=self.group) if ep.name == name]
        if len(matches) != 1:
            raise ValueError(
                f"Expected one installed {self.group} entry point for {name}, found {len(matches)}"
            )
        return matches[0].load()

    def get(self, name: str):
        return self.resolve(name)
