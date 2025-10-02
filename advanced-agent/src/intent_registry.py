import re
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class IntentRule:
    name: str
    keywords: List[str]
    pricing_curated: Dict[str, List[str]]
    banned_domains: Optional[List[str]] = None

    def match(self, query: str, pricing: str) -> bool:
        query_lower = query.lower()
        tokens = set(re.findall(r"[a-z0-9]+", query_lower))
        for keyword in self.keywords:
            key_lower = keyword.lower()
            if " " in key_lower:
                if key_lower not in query_lower:
                    return False
            else:
                if key_lower not in tokens:
                    return False
        return True

    def fetch(self, pricing: str) -> Optional[List[str]]:
        key = pricing.lower()
        tools = self.pricing_curated.get(key) or self.pricing_curated.get("any")
        if not tools:
            return None
        if not self.banned_domains:
            return tools
        filtered = []
        for tool in tools:
            url = tool.strip()
            if any(domain in url.lower() for domain in self.banned_domains):
                continue
            filtered.append(url)
        return filtered or tools


class IntentRegistry:
    def __init__(self):
        code_editor_curated = {
            "any": [
                "Visual Studio Code",
                "Visual Studio",
                "JetBrains IntelliJ IDEA",
                "JetBrains PyCharm",
                "JetBrains WebStorm",
                "JetBrains Rider",
                "Sublime Text",
                "Atom",
                "VSCodium",
                "Eclipse IDE",
                "NetBeans",
                "GNU Emacs",
                "Vim",
            ],
            "free": [
                "Visual Studio Code",
                "VSCodium",
                "Atom",
                "Eclipse IDE",
                "NetBeans",
                "GNU Emacs",
                "Vim",
            ],
            "paid": [
                "JetBrains IntelliJ IDEA",
                "JetBrains PyCharm",
                "JetBrains WebStorm",
                "JetBrains Rider",
                "Sublime Text",
                "Visual Studio Professional",
                "Visual Studio Enterprise",
            ],
            "freemium": [
                "Visual Studio",
                "Replit",
                "AWS Cloud9",
                "GitHub Codespaces",
                "Codesandbox",
            ],
        }

        vscode_alternatives_curated = {
            "any": [
                "VSCodium",
                "Sublime Text",
                "JetBrains IntelliJ IDEA",
                "JetBrains PyCharm",
                "JetBrains WebStorm",
                "JetBrains Rider",
                "Atom",
                "Eclipse IDE",
                "NetBeans",
                "GNU Emacs",
                "Vim",
            ],
            "free": [
                "VSCodium",
                "Atom",
                "Eclipse IDE",
                "NetBeans",
                "GNU Emacs",
                "Vim",
            ],
            "paid": [
                "JetBrains IntelliJ IDEA",
                "JetBrains PyCharm",
                "JetBrains WebStorm",
                "JetBrains Rider",
                "Sublime Text",
                "Visual Studio Professional",
                "Visual Studio Enterprise",
            ],
            "freemium": [
                "Visual Studio",
                "Replit",
                "AWS Cloud9",
                "GitHub Codespaces",
                "Codesandbox",
            ],
        }

        self._rules: List[IntentRule] = [
            IntentRule(
                name="paid-python-web-frameworks",
                keywords=["paid", "python", "web", "framework"],
                pricing_curated={
                    "paid": [
                        "Odoo Enterprise",
                        "Anvil",
                        "Taipy Enterprise",
                        "Dash Enterprise",
                        "Shiny for Python",
                        "Streamlit Cloud",
                        "Enthought Canopy",
                        "Divio",
                    ]
                },
            ),
            IntentRule(
                name="oss-machine-learning",
                keywords=["machine", "learning"],
                pricing_curated={
                    "free": [
                        "TensorFlow",
                        "PyTorch",
                        "Scikit-learn",
                        "Keras",
                        "XGBoost",
                        "LightGBM",
                        "CatBoost",
                        "Hugging Face Transformers",
                    ],
                    "any": [
                        "TensorFlow",
                        "PyTorch",
                        "Scikit-learn",
                        "Keras",
                        "XGBoost",
                        "LightGBM",
                        "CatBoost",
                        "Hugging Face Transformers",
                    ],
                },
            ),
            IntentRule(
                name="cloud-services",
                keywords=["cloud"],
                pricing_curated={
                    "paid": [
                        "Amazon Web Services",
                        "Microsoft Azure",
                        "Google Cloud Platform",
                        "IBM Cloud",
                        "Oracle Cloud Infrastructure",
                        "Alibaba Cloud",
                        "VMware Cloud",
                        "Salesforce Heroku Enterprise",
                    ],
                    "free": [
                        "AWS Free Tier",
                        "Google Cloud Free Program",
                        "Azure Free Account",
                        "Oracle Cloud Free Tier",
                        "IBM Cloud Lite",
                        "Netlify Free",
                        "Vercel Hobby",
                        "Render Free",
                    ],
                    "freemium": [
                        "Heroku",
                        "Netlify",
                        "Vercel",
                        "Render",
                        "Firebase",
                        "DigitalOcean App Platform",
                        "Railway",
                        "Fly.io",
                    ],
                    "any": [
                        "Amazon Web Services",
                        "Microsoft Azure",
                        "Google Cloud Platform",
                        "IBM Cloud",
                        "Oracle Cloud Infrastructure",
                        "Alibaba Cloud",
                        "DigitalOcean",
                        "Linode",
                    ],
                },
            ),
            IntentRule(
                name="aws-cloud-services",
                keywords=["aws"],
                pricing_curated={
                    "any": [
                        "Amazon EC2",
                        "Amazon S3",
                        "AWS Lambda",
                        "Amazon RDS",
                        "Amazon DynamoDB",
                        "Amazon CloudFront",
                        "Amazon EKS",
                        "Amazon SageMaker",
                    ],
                    "paid": [
                        "Amazon EC2",
                        "Amazon S3",
                        "AWS Lambda",
                        "Amazon RDS",
                        "Amazon DynamoDB",
                        "Amazon CloudFront",
                        "Amazon EKS",
                        "Amazon Redshift",
                    ],
                    "freemium": [
                        "AWS Free Tier",
                        "AWS Lambda",
                        "Amazon S3",
                        "AWS Amplify",
                        "Amazon CloudWatch",
                        "AWS Glue",
                    ],
                    "free": [
                        "AWS Free Tier",
                        "AWS Lambda Free Tier",
                        "Amazon S3 Free Tier",
                        "AWS Educate",
                        "AWS Activate Founders",
                        "AWS Lightsail Free Tier",
                    ],
                },
            ),
            IntentRule(
                name="azure-cloud-services",
                keywords=["azure"],
                pricing_curated={
                    "any": [
                        "Azure Virtual Machines",
                        "Azure App Service",
                        "Azure Functions",
                        "Azure Kubernetes Service",
                        "Azure SQL Database",
                        "Azure Cosmos DB",
                        "Azure Blob Storage",
                        "Azure DevOps",
                    ],
                    "paid": [
                        "Azure Virtual Machines",
                        "Azure App Service",
                        "Azure Kubernetes Service",
                        "Azure SQL Database",
                        "Azure Cosmos DB",
                        "Azure Synapse Analytics",
                        "Azure Machine Learning",
                        "Azure Cognitive Services",
                    ],
                    "freemium": [
                        "Azure Free Account",
                        "Azure Functions",
                        "Azure App Service",
                        "Azure Cosmos DB",
                        "Azure DevOps",
                        "Azure Monitor",
                    ],
                    "free": [
                        "Azure Free Account",
                        "Azure for Students",
                        "Azure Functions Free Tier",
                        "Azure App Service Free Tier",
                        "Azure DevOps Free Tier",
                        "GitHub Actions for Azure",
                    ],
                },
            ),
            IntentRule(
                name="paid-kubernetes-tools",
                keywords=["paid", "kubernetes"],
                pricing_curated={
                    "paid": [
                        "Kubecost Enterprise",
                        "Rafay Kubernetes Management Platform",
                        "Red Hat OpenShift",
                        "SUSE Rancher Prime",
                        "Mirantis Kubernetes Engine",
                        "VMware Tanzu Kubernetes Grid",
                        "Spectro Cloud Palette",
                        "Nirmata Kubernetes Platform",
                        "Platform9 Managed Kubernetes"
                    ],
                    "enterprise": [
                        "Red Hat OpenShift",
                        "SUSE Rancher Prime",
                        "Mirantis Kubernetes Engine",
                        "VMware Tanzu Kubernetes Grid",
                        "Spectro Cloud Palette",
                        "Rafay Kubernetes Management Platform",
                        "Kubecost Enterprise"
                    ]
                },
            ),
            IntentRule(
                name="code-editors",
                keywords=["code", "editor"],
                pricing_curated=code_editor_curated,
            ),
            IntentRule(
                name="ide-code-editors",
                keywords=["ide"],
                pricing_curated=code_editor_curated,
            ),
            IntentRule(
                name="ides-code-editors",
                keywords=["ides"],
                pricing_curated=code_editor_curated,
            ),
            IntentRule(
                name="vscode-alternatives",
                keywords=["vs", "code", "alternatives"],
                pricing_curated=vscode_alternatives_curated,
            ),
            IntentRule(
                name="vscode-compact-alternatives",
                keywords=["vscode", "alternatives"],
                pricing_curated=vscode_alternatives_curated,
            ),
            IntentRule(
                name="visual-studio-code-alternatives",
                keywords=["visual", "studio", "code", "alternatives"],
                pricing_curated=vscode_alternatives_curated,
            ),
            IntentRule(
                name="swift-frameworks",
                keywords=["swift", "framework"],
                banned_domains=["archives.gov", "fda.gov"],
                pricing_curated={
                    "paid": [
                        "https://supernova.io/",
                        "https://designcode.io/swiftui",
                        "https://www.swiftstarterkit.com/",
                        "https://shapeof.com/collection/swiftui",
                        "https://www.mongodb.com/realm",
                        "https://perfect.org/cloud/",
                    ],
                    "freemium": [
                        "https://firebase.google.com/",
                        "https://www.revenuecat.com/",
                        "https://onesignal.com/",
                        "https://getstream.io/chat/sdk/ios/",
                        "https://appcenter.ms/",
                    ],
                    "free": [
                        "https://developer.apple.com/documentation/swiftui",
                        "https://developer.apple.com/documentation/uikit",
                        "https://developer.apple.com/documentation/combine",
                        "https://docs.vapor.codes/",
                        "https://www.kitura.dev/",
                        "https://alamofire.github.io/Alamofire/",
                        "https://github.com/apple/swift-nio",
                        "https://www.mongodb.com/docs/realm/sdk/swift/",
                        "https://swiftpackageindex.com/search?query=swift",
                    ],
                    "any": [
                        "https://developer.apple.com/documentation/swiftui",
                        "https://developer.apple.com/documentation/uikit",
                        "https://developer.apple.com/documentation/combine",
                        "https://docs.vapor.codes/",
                        "https://www.kitura.dev/",
                        "https://alamofire.github.io/Alamofire/",
                        "https://github.com/apple/swift-nio",
                        "https://www.mongodb.com/docs/realm/sdk/swift/",
                        "https://swiftpackageindex.com/search?query=swift",
                    ],
                },
            ),
        ]

    def match(self, query: str, pricing: str) -> Optional[IntentRule]:
        for rule in self._rules:
            if rule.match(query, pricing):
                return rule
        return None
