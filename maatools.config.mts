import type { FullConfig } from '@nekosu/maa-tools'

const config: FullConfig = {
  cwd: import.meta.dirname,
  maaVersion: 'latest',
  interfacePath: 'assets/interface.json',
  check: {
    override: {
      // MPE 编辑器写入的 $__mpe_config_* 会报 warning；不忽略会导致 CI exit 1
      'mpe-config': 'ignore'
    }
  }
}

export default config
