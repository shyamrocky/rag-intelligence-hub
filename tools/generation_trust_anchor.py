"""Deployment trust root. Only an owner-reviewed source release may change this registry.

Intentionally outside the manifest's self-hash graph. Independently pinned in the
release review seal and every owner authorization's implementation bindings.
There is no runtime command to approve or generate replacement trust roots.
"""
TRUSTED_BASELINES = {
    "data/evals/generation-trust/v1/MANIFEST.json": "70228597a2f2281f348d690cb6293ed598f2dc5170328e2b7b5d78856370b45a",
    "data/evals/generation-trust/v2/MANIFEST.json": "bc30c4f03e0fabf2a658b6653f9f5c10121895b30413e6524d95662eb2ccc566",
    "data/evals/generation-trust/v3/MANIFEST.json": "9644445349835be41414db286d96cbc392bddd675ff6212db8d344911059d4f7",
    "data/evals/generation-trust/v4/MANIFEST.json": "5283269f3cd7a9a59f3e2ea742f79b6d051b2afb28d0549bceb1028a98b32b91",
    "data/evals/generation-trust/v5/MANIFEST.json": "b124e839f370abc505dbe485eba1dc627aaec06d9cd8502a7c6c60fda2313c93",
    "data/evals/generation-trust/v6/MANIFEST.json": "38b73f5b0311f16bc1c0237cfac618a17615d24a394019e3978296397b42aaef",
    "data/evals/generation-trust/v7/MANIFEST.json": "cc116a5f05eff84b868c6da1154477a6acb5232a0498c994f74cc5855227af9c",
    "data/evals/generation-trust/v8/MANIFEST.json": "27bda51dd995979b4c7e5f9165fdc2cba6b0aea831a93bc87c7ba4ade0ae61f4",
    "data/evals/generation-trust/v9/MANIFEST.json": "16380fb013b52f19abd098d31de6edf690b72d905df4a6e10af7a8e7d638f990",
    "data/evals/generation-trust/v10/MANIFEST.json": "982d512a2d07a39717bd64a91dbddc2822f6b289b4636d83d8e98eab7f706143",
    "data/evals/generation-trust/v11/MANIFEST.json": "d8b14335d2bd8c0b77fac982939a524ad3f1d9707f3d0bfe788c038296fcf0c8",
    "data/evals/generation-trust/v12/MANIFEST.json": "f4c49eaa16b3cd4e678761831ace3b5561b631aa2270c19635873badc7326039",
    "data/evals/generation-trust/v13/MANIFEST.json": "7f414058bd2be6f85dda86e7565d117e14419159024c82e7a2b69613885f5023",
    "data/evals/generation-trust/v14/MANIFEST.json": "0aca9358c8563e0e952538c6768cf43f0ed0c9e455424ace48c83d7c41a8ffd9",
    "data/evals/generation-trust/v15/MANIFEST.json": "4afefb2d2158f0737704563e428de594c9638b954a4782ec9f04de1cd3080142",
    "data/evals/generation-trust/v16/MANIFEST.json": "671d3744a8ce22aa86e406bd4a4a805d35a0b272960b5c174b52397619fd3233",
    "data/evals/generation-trust/v17/MANIFEST.json": "b2a11f30bde952858dbc7e8a5eac3fff5f363bcb3e7ff2a7810d9a7d769cef9e",
    "data/evals/generation-trust/v18/MANIFEST.json": "9b77f6225390d9e69f06e70c6157ec4b907e55aa2c48edd30c65780f46931c2f",
    "data/evals/generation-trust/v19/MANIFEST.json": "148b3a34d51a45232d2d6a3d046a20c789222aa89e1587f384ae834cb85cf959",
    "data/evals/generation-trust/v20/MANIFEST.json": "fddfa9a53ebcbd7378234dd31af6c47e7b88cc4965ffbbfcf96725855a6d80d0",
    "data/evals/generation-trust/v21/MANIFEST.json": "5e896f5dd43d6e1a21ad55a36bf51d4915d6c3da6b7611d033095137b1b3bf01",
    "data/evals/generation-trust/v22/MANIFEST.json": "ac5f252e19b0d8ae61959f14ac3e2805a266f513df424e2cb5855dcffd5950e8",
    "data/evals/generation-trust/v23/MANIFEST.json": "45bb60efdf468cf84a6518c7b719bec03b39342a41629c908d064bcb78a237be",
    "data/evals/generation-trust/v24/MANIFEST.json": "f5b2fb4bb2bec128fa6155efe1ef72248d3cc59f326ffe2004a5bf4b2fae64c0",
    "data/evals/generation-trust/v25/MANIFEST.json": "1a80b6860758a73a102a76bdd5ad4799165f1863577085f275af2630df50be0f",
    "data/evals/generation-trust/v26/MANIFEST.json": "c73a91988b61d76c99ff158abf0f05339e894fcea86784afd58508596d167a68",
    "data/evals/generation-trust/v27/MANIFEST.json": "7db247c70dcca07bcf5f6ae79caba2393886155e2b9959679e1c410afe7f1771",
    "data/evals/generation-trust/v28/MANIFEST.json": "f3bcff5f4576a8dbfcf3ba2f8ce623ebece21518acde09cad4919613ecca5f58",
    "data/evals/generation-trust/v29/MANIFEST.json": "38f1f71da2aeb81e3be2d82ad62de8f66813370892aa717df84d983840a7b573",
    "data/evals/generation-trust/v30/MANIFEST.json": "379e113d399f20923c8e029011da970122db383c8a398d75f1eb24976427202c",
    "data/evals/generation-trust/v31/MANIFEST.json": "2827ad25a5e4768c9de6893476d9db2ac24809d54a658d1f4dd3109855d0931c",
    "data/evals/generation-trust/v32/MANIFEST.json": "30e4bba180f96217aeee16453f4f7855aefb65638bdde339eb522b5e93713fd6",
    "data/evals/generation-trust/v33/MANIFEST.json": "c995091a74368c2183946630c3c2feab402c32524e94365d633267cfc77cca70",
    'data/evals/generation-trust/v34/MANIFEST.json': 'e5a3eddddd97781c25139d31c923ced00966b0c06b13d7b2f5d3b86c49db104d',
    'data/evals/generation-trust/v35/MANIFEST.json': '172016e1322a4f591d3f2f7217a8a1b1b626fce76c105a26d8d17ac5ac585f05',
    'data/evals/generation-trust/v36/MANIFEST.json': '96db25147962afa6927d028de963b9f9b2e0141e394e934fad0c248b15f08af4',
    'data/evals/generation-trust/v37/MANIFEST.json': 'f671f0cf4549f3d244ab7ff90f9fae5ac22b217b6aff62f13a5faa1ab9ffdd16',
    'data/evals/generation-trust/v38/MANIFEST.json': '876880c7fa04ad79da51644ed589cb421167fbb32786007d6af2058d861d03c9',

    'data/evals/generation-trust/v39/MANIFEST.json': 'd5137c388e0655c1f057f420cec871bcc045a1ed6cfcb78c9bc527baaf5b107b',
    'data/evals/generation-trust/v40/MANIFEST.json': 'e48eda5690673ffb72599f1e7224fd5f6f9df0590d3aec632be04208f53d5772',
    'data/evals/generation-trust/v41/MANIFEST.json': 'ab3fd1415caffc841007f32479633b79426b77a70bd254cd2bd76fc2cd63f443',
    'data/evals/generation-trust/v42/MANIFEST.json': 'd3f49cfedce5bcfca22794e4572fd7153d620a90cbfefa0bc6c2999f8abb6ed9',
    'data/evals/generation-trust/v43/MANIFEST.json': '6f816a9c14db325622ad7c998d25a06d237194918e240123fb7c7615a9612dba',

    'data/evals/generation-trust/v44/MANIFEST.json': 'a51c8fc50e4812a42e0c7722b8689102c7c271a16b5948d941ebf407d288cac7',
    'data/evals/generation-trust/v45/MANIFEST.json': 'e13c31a086ec2108dd6e1bb43143fa7d5d789fbeae1c08b753ff26f9096c9dc0',
    'data/evals/generation-trust/v46/MANIFEST.json': 'e503fd538b1ded67cef23a8946b648c52caf7c5945c9bb7e3347c47032069730',
    'data/evals/generation-trust/v47/MANIFEST.json': '8a0ae5655744d92bdf0ff0801be0e52181a640bfd6528612090dca226860fbcb',
    'data/evals/generation-trust/v48/MANIFEST.json': '2c1e2103e5d88634bfb203d32ab95eae888b91ebaa953271bcc2737478853bac',

    'data/evals/generation-trust/v49/MANIFEST.json': '5ebac608ced8441d8a62a10451ec836ffe90610502c728eb230dcb6c2bf75b0b',
    'data/evals/generation-trust/v50/MANIFEST.json': 'fe24e9418b7ef3084c4540ae5bd77bfc17ebcae57eb792cc270dff94a1603f54',
    'data/evals/generation-trust/v51/MANIFEST.json': '73a3b6be21edcf18a5195901609009e278f665507925127f79b1afb21c762f9b',
    'data/evals/generation-trust/v52/MANIFEST.json': '8e009cd989c89de9ccaef87d591fed1a170123604125d4fdbd1227ff9d752deb',
    'data/evals/generation-trust/v53/MANIFEST.json': '400556e4ff931ff35e9a367d4c2be0ecd1f4806fc2007ea6c575970998178fc7',

    'data/evals/generation-trust/v54/MANIFEST.json': '16f3e51fcece5bc49db4a9a086f232b8e9f10c2ebe570c20bf52d83d9f4e0cb6',
    'data/evals/generation-trust/v55/MANIFEST.json': '7e10f6a4aa64340d5236873f06a5cb8774d61d1e0e0d514def913adcf32651f4',
    'data/evals/generation-trust/v56/MANIFEST.json': '068ccf6b3a67d9f397498dcdddd34538826302df1d250802e75935932b9d5eb7',
    'data/evals/generation-trust/v57/MANIFEST.json': '60131e7e844be0be0f819fa30ca565d3fdd97927c6cf894c53821add66c40cac',
    'data/evals/generation-trust/v58/MANIFEST.json': 'f995c76af1651fa406ca3b98a0200dc3b357a7d3b165d20bbc818283cc0f68b0',

    'data/evals/generation-trust/v59/MANIFEST.json': 'd56f918db7ffabaea6f1509bb453435f315598f881032b26c76156d1e79bb3ac',
    'data/evals/generation-trust/v60/MANIFEST.json': '49d23d4e65b544f23d3cb78aed69ac5149173f6a620eb2e8dc11caa676f3f228',
    'data/evals/generation-trust/v61/MANIFEST.json': '44475511fbeb0a8097a71c94df5e0a4fd698cb0e5ac47e58d96464cc6ea35d39',
    'data/evals/generation-trust/v62/MANIFEST.json': '30dc8b2712144c3a489f09552b11d119353401baac8eebdc1a6fea26cde33860',
    'data/evals/generation-trust/v63/MANIFEST.json': '658d4de39158e53beaef5f3efea6c8db835cbda91c76b615d7c95f86f4a768da',

    'data/evals/generation-trust/v64/MANIFEST.json': '7b1fca21b2c6f2a7e49ca5fac37ed203c03a98ebc4b29d95d1ad848f37dc12cd',
    'data/evals/generation-trust/v65/MANIFEST.json': '55ed300f10ca9b599ce0ee87d25c31dcd597caacae835600f3d0370d30b5d9fa',
    'data/evals/generation-trust/v66/MANIFEST.json': '6ad41904d385d4818e2f08bcd522931419ca06e671689484be37f5023bfe21b6',
    'data/evals/generation-trust/v67/MANIFEST.json': '2e3116c7c7c37904b112b2757047f2c69ec19353655c98cdf2d7f921adef6ab0',
    'data/evals/generation-trust/v68/MANIFEST.json': '60bc0480b2bcdad81c1544ed72ebaa63ebf2b4dfd3a05ce54b56989c132d88f0',
    'data/evals/generation-trust/v69/MANIFEST.json': '1a67c4102525df0db8ab5d75fb012627512de5ee840f5559b42cedf3a4886cd2',
    'data/evals/generation-trust/v70/MANIFEST.json': '6fee7c8912a03de0e1e616ad85d46e885aa46c019c43fa2723a39074e38a5ea3',
    'data/evals/generation-trust/v71/MANIFEST.json': 'bf40177ef88487fc300892a60945c8a8543882a6d2da9d2461b581cf639b50bf',
    'data/evals/generation-trust/v72/MANIFEST.json': '04a509928be4322dc377b174b338f8b75061072aa301d26f6a7e916e2a74acb4',
    'data/evals/generation-trust/v73/MANIFEST.json': '52f7d66fdc06b5bfc60437c5a0e9389a48161b56ec4b494898cf780493db81f2',
    'data/evals/generation-trust/v74/MANIFEST.json': 'e57f2d910afc39b54bc287c732a5fe925221ed50f12187c82ea100cf1b045739',
    'data/evals/generation-trust/v75/MANIFEST.json': '881b51fea1164c9469e1b33f1050c92538a44ff38dabfa68c90af0670e5dfe86',
    'data/evals/generation-trust/v76/MANIFEST.json': '05acf905089ad91b894294b6e36f0e647d423bf0dfb9ef55118c2c1d670cd272',
    'data/evals/generation-trust/v77/MANIFEST.json': '7759525a354e3f0644daccc44a388616388aa7a574b3fa3816b099e3292cc986',
    'data/evals/generation-trust/v78/MANIFEST.json': '2bdd7fe4efaff4e21ceada7022947123d27db2624073f99c37daa0b7f6e049e4',
    'data/evals/generation-trust/v79/MANIFEST.json': 'dad45ac78f1fa279343a17ee53931792628eca8b3f19088db82953528c7b5b6f',
    'data/evals/generation-trust/v80/MANIFEST.json': 'a8b059babadc5e22b00d16a22404d65f951029bb4b2d8413bfd9f6b2757a1fc7',
    'data/evals/generation-trust/v81/MANIFEST.json': '519f76848da8575f731fbb81355323b657a0df0e735d0c3810299625209c110a',
    'data/evals/generation-trust/v82/MANIFEST.json': 'b05e51047c9a81d79b82be334eac6f3fb3465ff50af629d83c70aaec5f257423',
    'data/evals/generation-trust/v83/MANIFEST.json': '7c22ff97515ea058725ea31538c7aec56d0c8780d0c15fa0b88961d30afb3f87',
    'data/evals/generation-trust/v84/MANIFEST.json': 'be9871c01f2caee10b00abe421a3215018f9639f265f486b5f960123643c5095',

}

# Review preparation only; no paid-execution authority.
HUMAN_REVIEW_BASELINE = "data/evals/generation-trust/v84/MANIFEST.json"

# Review-only exact migrations. Native paid authorization never consults this map.
HUMAN_REVIEW_TRUST_MIGRATIONS = {'data/evals/generation-trust/v25/MANIFEST.json': {'parent_sha256': '1a80b6860758a73a102a76bdd5ad4799165f1863577085f275af2630df50be0f', 'successor': {'path': 'data/evals/generation-trust/v39/MANIFEST.json', 'sha256': 'd5137c388e0655c1f057f420cec871bcc045a1ed6cfcb78c9bc527baaf5b107b'}}, 'data/evals/generation-trust/v39/MANIFEST.json': {'parent_sha256': 'd5137c388e0655c1f057f420cec871bcc045a1ed6cfcb78c9bc527baaf5b107b', 'successor': {'path': 'data/evals/generation-trust/v44/MANIFEST.json', 'sha256': 'a51c8fc50e4812a42e0c7722b8689102c7c271a16b5948d941ebf407d288cac7'}}, 'data/evals/generation-trust/v44/MANIFEST.json': {'parent_sha256': 'a51c8fc50e4812a42e0c7722b8689102c7c271a16b5948d941ebf407d288cac7', 'successor': {'path': 'data/evals/generation-trust/v49/MANIFEST.json', 'sha256': '5ebac608ced8441d8a62a10451ec836ffe90610502c728eb230dcb6c2bf75b0b'}}, 'data/evals/generation-trust/v49/MANIFEST.json': {'parent_sha256': '5ebac608ced8441d8a62a10451ec836ffe90610502c728eb230dcb6c2bf75b0b', 'successor': {'path': 'data/evals/generation-trust/v54/MANIFEST.json', 'sha256': '16f3e51fcece5bc49db4a9a086f232b8e9f10c2ebe570c20bf52d83d9f4e0cb6'}}, 'data/evals/generation-trust/v54/MANIFEST.json': {'parent_sha256': '16f3e51fcece5bc49db4a9a086f232b8e9f10c2ebe570c20bf52d83d9f4e0cb6', 'successor': {'path': 'data/evals/generation-trust/v59/MANIFEST.json', 'sha256': 'd56f918db7ffabaea6f1509bb453435f315598f881032b26c76156d1e79bb3ac'}}, 'data/evals/generation-trust/v59/MANIFEST.json': {'parent_sha256': 'd56f918db7ffabaea6f1509bb453435f315598f881032b26c76156d1e79bb3ac', 'successor': {'path': 'data/evals/generation-trust/v64/MANIFEST.json', 'sha256': '7b1fca21b2c6f2a7e49ca5fac37ed203c03a98ebc4b29d95d1ad848f37dc12cd'}}}

# Offline Bot scope only; no live-generation authority.
BOT_RUNTIME_BASELINE = "data/evals/generation-trust/v84/MANIFEST.json"
HUMAN_REVIEW_TRUST_MIGRATIONS["data/evals/generation-trust/v64/MANIFEST.json"] = {'parent_sha256': '7b1fca21b2c6f2a7e49ca5fac37ed203c03a98ebc4b29d95d1ad848f37dc12cd', 'successor': {'path': 'data/evals/generation-trust/v65/MANIFEST.json', 'sha256': '55ed300f10ca9b599ce0ee87d25c31dcd597caacae835600f3d0370d30b5d9fa'}}

HUMAN_REVIEW_TRUST_MIGRATIONS["data/evals/generation-trust/v65/MANIFEST.json"] = {'parent_sha256': '55ed300f10ca9b599ce0ee87d25c31dcd597caacae835600f3d0370d30b5d9fa', 'successor': {'path': 'data/evals/generation-trust/v66/MANIFEST.json', 'sha256': '6ad41904d385d4818e2f08bcd522931419ca06e671689484be37f5023bfe21b6'}}

HUMAN_REVIEW_TRUST_MIGRATIONS["data/evals/generation-trust/v66/MANIFEST.json"] = {'parent_sha256': '6ad41904d385d4818e2f08bcd522931419ca06e671689484be37f5023bfe21b6', 'successor': {'path': 'data/evals/generation-trust/v67/MANIFEST.json', 'sha256': '2e3116c7c7c37904b112b2757047f2c69ec19353655c98cdf2d7f921adef6ab0'}}

HUMAN_REVIEW_TRUST_MIGRATIONS["data/evals/generation-trust/v67/MANIFEST.json"] = {'parent_sha256': '2e3116c7c7c37904b112b2757047f2c69ec19353655c98cdf2d7f921adef6ab0', 'successor': {'path': 'data/evals/generation-trust/v68/MANIFEST.json', 'sha256': '60bc0480b2bcdad81c1544ed72ebaa63ebf2b4dfd3a05ce54b56989c132d88f0'}}

HUMAN_REVIEW_TRUST_MIGRATIONS["data/evals/generation-trust/v68/MANIFEST.json"] = {'parent_sha256': '60bc0480b2bcdad81c1544ed72ebaa63ebf2b4dfd3a05ce54b56989c132d88f0', 'successor': {'path': 'data/evals/generation-trust/v69/MANIFEST.json', 'sha256': '1a67c4102525df0db8ab5d75fb012627512de5ee840f5559b42cedf3a4886cd2'}}

HUMAN_REVIEW_TRUST_MIGRATIONS["data/evals/generation-trust/v69/MANIFEST.json"] = {'parent_sha256': '1a67c4102525df0db8ab5d75fb012627512de5ee840f5559b42cedf3a4886cd2', 'successor': {'path': 'data/evals/generation-trust/v70/MANIFEST.json', 'sha256': '6fee7c8912a03de0e1e616ad85d46e885aa46c019c43fa2723a39074e38a5ea3'}}

HUMAN_REVIEW_TRUST_MIGRATIONS["data/evals/generation-trust/v70/MANIFEST.json"] = {'parent_sha256': '6fee7c8912a03de0e1e616ad85d46e885aa46c019c43fa2723a39074e38a5ea3', 'successor': {'path': 'data/evals/generation-trust/v71/MANIFEST.json', 'sha256': 'bf40177ef88487fc300892a60945c8a8543882a6d2da9d2461b581cf639b50bf'}}

HUMAN_REVIEW_TRUST_MIGRATIONS["data/evals/generation-trust/v71/MANIFEST.json"] = {'parent_sha256': 'bf40177ef88487fc300892a60945c8a8543882a6d2da9d2461b581cf639b50bf', 'successor': {'path': 'data/evals/generation-trust/v74/MANIFEST.json', 'sha256': 'e57f2d910afc39b54bc287c732a5fe925221ed50f12187c82ea100cf1b045739'}}

HUMAN_REVIEW_TRUST_MIGRATIONS["data/evals/generation-trust/v74/MANIFEST.json"] = {'parent_sha256': 'e57f2d910afc39b54bc287c732a5fe925221ed50f12187c82ea100cf1b045739', 'successor': {'path': 'data/evals/generation-trust/v75/MANIFEST.json', 'sha256': '881b51fea1164c9469e1b33f1050c92538a44ff38dabfa68c90af0670e5dfe86'}}

HUMAN_REVIEW_TRUST_MIGRATIONS["data/evals/generation-trust/v75/MANIFEST.json"] = {'parent_sha256': '881b51fea1164c9469e1b33f1050c92538a44ff38dabfa68c90af0670e5dfe86', 'successor': {'path': 'data/evals/generation-trust/v76/MANIFEST.json', 'sha256': '05acf905089ad91b894294b6e36f0e647d423bf0dfb9ef55118c2c1d670cd272'}}

HUMAN_REVIEW_TRUST_MIGRATIONS["data/evals/generation-trust/v76/MANIFEST.json"] = {'parent_sha256': '05acf905089ad91b894294b6e36f0e647d423bf0dfb9ef55118c2c1d670cd272', 'successor': {'path': 'data/evals/generation-trust/v77/MANIFEST.json', 'sha256': '7759525a354e3f0644daccc44a388616388aa7a574b3fa3816b099e3292cc986'}}

HUMAN_REVIEW_TRUST_MIGRATIONS["data/evals/generation-trust/v77/MANIFEST.json"] = {'parent_sha256': '7759525a354e3f0644daccc44a388616388aa7a574b3fa3816b099e3292cc986', 'successor': {'path': 'data/evals/generation-trust/v78/MANIFEST.json', 'sha256': '2bdd7fe4efaff4e21ceada7022947123d27db2624073f99c37daa0b7f6e049e4'}}

HUMAN_REVIEW_TRUST_MIGRATIONS["data/evals/generation-trust/v78/MANIFEST.json"] = {'parent_sha256': '2bdd7fe4efaff4e21ceada7022947123d27db2624073f99c37daa0b7f6e049e4', 'successor': {'path': 'data/evals/generation-trust/v79/MANIFEST.json', 'sha256': 'dad45ac78f1fa279343a17ee53931792628eca8b3f19088db82953528c7b5b6f'}}

HUMAN_REVIEW_TRUST_MIGRATIONS["data/evals/generation-trust/v79/MANIFEST.json"] = {'parent_sha256': 'dad45ac78f1fa279343a17ee53931792628eca8b3f19088db82953528c7b5b6f', 'successor': {'path': 'data/evals/generation-trust/v80/MANIFEST.json', 'sha256': 'a8b059babadc5e22b00d16a22404d65f951029bb4b2d8413bfd9f6b2757a1fc7'}}

HUMAN_REVIEW_TRUST_MIGRATIONS["data/evals/generation-trust/v80/MANIFEST.json"] = {'parent_sha256': 'a8b059babadc5e22b00d16a22404d65f951029bb4b2d8413bfd9f6b2757a1fc7', 'successor': {'path': 'data/evals/generation-trust/v81/MANIFEST.json', 'sha256': '519f76848da8575f731fbb81355323b657a0df0e735d0c3810299625209c110a'}}

HUMAN_REVIEW_TRUST_MIGRATIONS["data/evals/generation-trust/v81/MANIFEST.json"] = {'parent_sha256': '519f76848da8575f731fbb81355323b657a0df0e735d0c3810299625209c110a', 'successor': {'path': 'data/evals/generation-trust/v82/MANIFEST.json', 'sha256': 'b05e51047c9a81d79b82be334eac6f3fb3465ff50af629d83c70aaec5f257423'}}

HUMAN_REVIEW_TRUST_MIGRATIONS["data/evals/generation-trust/v82/MANIFEST.json"] = {'parent_sha256': 'b05e51047c9a81d79b82be334eac6f3fb3465ff50af629d83c70aaec5f257423', 'successor': {'path': 'data/evals/generation-trust/v83/MANIFEST.json', 'sha256': '7c22ff97515ea058725ea31538c7aec56d0c8780d0c15fa0b88961d30afb3f87'}}

HUMAN_REVIEW_TRUST_MIGRATIONS["data/evals/generation-trust/v83/MANIFEST.json"] = {'parent_sha256': '7c22ff97515ea058725ea31538c7aec56d0c8780d0c15fa0b88961d30afb3f87', 'successor': {'path': 'data/evals/generation-trust/v84/MANIFEST.json', 'sha256': 'be9871c01f2caee10b00abe421a3215018f9639f265f486b5f960123643c5095'}}
