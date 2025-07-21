from unittest import TestCase
from maintainer import GhPagesMaintainer
from git import Repo
import tempfile
import os


class GhPagesMaintainerTestCase(TestCase):
    pass

    def test_export_market_pe(self):
        gpm = GhPagesMaintainer.get_instance()
        gpm._export_market_pe('hsi', '../../StkGuru/public/api/market_pe/hsi.json')
        gpm._export_market_pe('spx', '../../StkGuru/public/api/market_pe/spx.json')

    def test_export_market_breadth(self):
        gpm = GhPagesMaintainer.get_instance()
        gpm._export_market_breadth('spx', '../../StkGuru/public/api/mbs/spx.json')

    def test_git(self):
        with tempfile.TemporaryDirectory(delete=False) as tmpdir:
            print(tmpdir)
            repo = Repo.clone_from('/Users/yuz/Downloads/git_test', tmpdir)
            # 2. Pull the latest code (should be up-to-date after clone)
            repo.git.checkout('main')
            repo.remotes.origin.pull()

            # 3. Run static export to the checked-out repo
            # self._export_static_json(tmpdir)
            print(repo.git.status())
            with open(os.path.join(tmpdir, 'test.txt'), 'w') as f:
                f.write('test')
            with open(os.path.join(tmpdir, 'a'), 'a') as f:
                f.write('test')
            print(repo.git.diff())

            # 4. Check for changes
            repo.git.add(A=True)
            if repo.is_dirty(untracked_files=True):
                repo.index.commit('Update static JSON exports')
                repo.remotes.origin.push()
                print(repo.git.show())
            else:
                # No changes to commit
                return True

    def test_update_gh_pages(self):
        gpm = GhPagesMaintainer.get_instance()
        gpm.update_gh_pages()