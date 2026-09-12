# Installing dc-dev-plugins

Add the marketplace once per machine (in Claude Code or Claude Desktop):

```
/plugin marketplace add datacraftdevelopment/dc-dev-plugins
```

Then install the plugins you want:

```
/plugin install fm-dc@dc-dev-plugins
/plugin install pm@dc-dev-plugins
```

To pull the latest shipped changes on a machine that already has it:

```
/plugin marketplace update dc-dev-plugins
```
