<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## family-not-adopted — this skill's family is enabled for you, not adopted here

`facts.plugin` is enabled in your user-scope agent settings, so it loads in every project,
but this project's committed `.apache-magpie.lock` floor does not list it.
That can be deliberate (`magpie-contributor-growth` is meant to run per maintainer), so nothing is changed.

1. **Tell the user in one line, then carry on with their request in the same turn:**

   > `<facts.plugin>` is not adopted in this project; it loads here from your user settings. `/magpie-setup:upgrade` can keep it or hide it here.

2. **Record that the hint was shown**, so it does not repeat:

```bash
PYTHONPATH="$(python3 -I -c 'import hashlib,os,sys;h,d,m,i=sys.argv[1:];r=os.path.realpath(os.curdir);s=os.stat(r);p=os.path.join(h,d,hashlib.sha256(r.encode()).hexdigest()[:16]);f=os.path.join(p,i);print(p if os.path.isdir(os.path.join(p,m)) and os.path.isfile(f) and open(f).read().split()==[str(s.st_dev),str(s.st_ino)] else h)' "$HOME/.cache/apache-magpie/preflight" projects setup_preflight root-id)" \
  python3 -P -m setup_preflight.local_families record --plugin <facts.plugin> --choice hinted
```

Never block the requested work on this, never change any settings file from here,
and if the command exits non-zero, say nothing more about it and carry on.
The keep-or-hide question itself belongs to `setup update` → *Reconcile the local agent settings*.
